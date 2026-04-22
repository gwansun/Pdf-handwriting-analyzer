#!/usr/bin/env python3
"""
PDF Handwriting Analyzer — CLI entry point.
Reads AnalyzerRequest JSON from stdin, writes AnalyzerResponse JSON to stdout.
"""
import json
import logging
import sys
from pathlib import Path

# Ensure src/ is on path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from common.config import CONFIDENCE_REVIEW_THRESHOLD, GLM_OCR_ENDPOINT, GEMMA_ENDPOINT, ErrorCode
from common.types import AnalyzerRequest, FieldResult, Summary
from common.validator import RequestValidationError, validate_json_request
from common.pdf_inspector import inspect_pdf, PDFInspectionError
from common.template_registry import TemplateRegistry
from common.template_matcher import find_best_match
from common.response_builder import (
    build_success_response,
    build_review_required_response,
    build_failure_response,
    build_unknown_template_response,
    build_unknown_filled_review_response,
    response_to_dict,
    ErrorDetail,
)
from extractors.field_router import route_and_extract
from confidence.scorer import compute_document_confidence
from template.document_role_classifier import classify_document_role, DocumentRole
from template.registration import register_blank_pdf
from template.unknown_fallback import extract_unknown_filled_pdf

# ─── Logging ─────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "analyzer.log"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("analyzer")


def _check_glm_available() -> bool:
    """Check if GLM-OCR server is reachable."""
    try:
        import httpx
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{GLM_OCR_ENDPOINT}/v1/models")
            return resp.status_code == 200
    except Exception:
        return False


def _check_gemma_available() -> bool:
    """Check if Gemma server is reachable."""
    try:
        import httpx
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{GEMMA_ENDPOINT}/v1/models")
            return resp.status_code == 200
    except Exception:
        return False


def analyze(request: dict) -> dict:
    """
    Full pipeline: validate → inspect → match → extract → respond.
    Takes a raw JSON dict from Email Manager, returns a contract-compliant JSON dict.
    """
    glm_available = _check_glm_available()
    gemma_available = _check_gemma_available()

    if not glm_available:
        logger.warning("GLM-OCR server not reachable — extraction will be stubbed")
    if not gemma_available:
        logger.warning("Gemma server not reachable — review will be stubbed")

    # ── Stage 1: Validation ──────────────────────────────────────────────────
    request_id = request.get("request_id", "unknown")
    job_id = request.get("job_id", "unknown")

    try:
        validated = validate_json_request(request)
    except RequestValidationError as e:
        error = e.to_error_detail()
        resp = build_failure_response(
            request_id=request_id,
            job_id=job_id,
            error=error,
        )
        return response_to_dict(resp)

    # ── Stage 2: Inspection ──────────────────────────────────────────────────
    try:
        inspection = inspect_pdf(validated.file.path)
    except PDFInspectionError as e:
        logger.error(f"PDF inspection failed: {e.message}")
        err = ErrorDetail(code=e.code, message=e.message, retryable=e.retryable)
        return response_to_dict(build_failure_response(
            request_id=validated.request_id,
            job_id=validated.job_id,
            error=err,
        ))

    # ── Stage 3: Template matching ───────────────────────────────────────────
    registry = TemplateRegistry()
    registry.load_all()

    match_result = find_best_match(inspection, registry)

    if match_result.template_match_status != "matched":
        # ── Lane 2/3: No template matched — classify document role ───────────────
        logger.info(f"No template match (score={match_result.match_score:.3f})")
        role_result = classify_document_role(inspection, pdf_path=validated.file.path)
        logger.info(
            f"Document role classification: role={role_result.role} "
            f"(confidence={role_result.confidence:.3f}), reasons={role_result.reasons}"
        )

        if role_result.role == DocumentRole.BLANK_TEMPLATE_CANDIDATE:
            # ── Lane 2: Blank PDF, no template artifacts → auto-register ─────────
            logger.info(f"Blank template candidate detected — running registration")
            reg_result = register_blank_pdf(
                pdf_path=validated.file.path,
                inspection=inspection,
                templates_dir=None,  # use default TEMPLATES_DIR
                activate=False,      # always start as draft
            )

            if reg_result.success:
                logger.info(
                    f"Template auto-registration succeeded: "
                    f"template_id={reg_result.template_id}, "
                    f"folder={reg_result.template_folder}, "
                    f"status={reg_result.activation_status}"
                )
                # Re-run matched-template extraction with the newly registered template
                # The registry has been reloaded, so find_best_match should now succeed
                match_result = find_best_match(inspection, registry)
                if match_result.template_match_status == "matched":
                    logger.info(
                        f"Re-matched after registration: "
                        f"template={match_result.template_id} (score={match_result.match_score:.3f})"
                    )
                    # Continue to normal matched-template extraction below
                else:
                    # Registration succeeded but re-match still failed — fall through
                    # to fallback lane rather than failing
                    logger.warning(
                        f"Template registered but re-match failed "
                        f"(score={match_result.match_score:.3f}) — using fallback lane"
                    )
                    fallback_result = extract_unknown_filled_pdf(
                        pdf_path=validated.file.path,
                        inspection=inspection,
                        glm_available=glm_available,
                    )
                    return response_to_dict(
                        build_unknown_filled_review_response(
                            request_id=validated.request_id,
                            job_id=validated.job_id,
                            page_count=inspection.page_count,
                            overall_confidence=fallback_result.overall_confidence,
                            field_count=fallback_result.field_count,
                            warnings=fallback_result.warnings,
                            error=ErrorDetail(
                                code="UNKNOWN_TEMPLATE",
                                message=(
                                    f"Template auto-registered ({reg_result.template_id}) "
                                    f"but extraction re-match failed. "
                                    "Manual review required."
                                ),
                                retryable=False,
                            ) if not fallback_result.success else None,
                        )
                    )
            else:
                # Registration failed — fall back to provisional extraction
                logger.error(
                    f"Template auto-registration failed: errors={reg_result.errors}"
                )
                fallback_result = extract_unknown_filled_pdf(
                    pdf_path=validated.file.path,
                    inspection=inspection,
                    glm_available=glm_available,
                )
                return response_to_dict(
                    build_unknown_filled_review_response(
                        request_id=validated.request_id,
                        job_id=validated.job_id,
                        page_count=inspection.page_count,
                        overall_confidence=fallback_result.overall_confidence,
                        field_count=fallback_result.field_count,
                        warnings=[
                            {
                                "code": "REGISTRATION_FAILED",
                                "message": (
                                    f"Template auto-registration failed: {'; '.join(reg_result.errors)}. "
                                    "Provisional extraction was used instead."
                                ),
                            },
                            *fallback_result.warnings,
                        ],
                    )
                )

        elif role_result.role == DocumentRole.FILLED_INSTANCE:
            # ── Lane 3: Filled PDF, no template match → provisional extraction ──
            logger.info(f"Unknown filled PDF — using provisional fallback extraction")
            fallback_result = extract_unknown_filled_pdf(
                pdf_path=validated.file.path,
                inspection=inspection,
                glm_available=glm_available,
            )
            return response_to_dict(
                build_unknown_filled_review_response(
                    request_id=validated.request_id,
                    job_id=validated.job_id,
                    page_count=inspection.page_count,
                    overall_confidence=fallback_result.overall_confidence,
                    field_count=fallback_result.field_count,
                    warnings=fallback_result.warnings,
                    error=ErrorDetail(
                        code="UNKNOWN_TEMPLATE",
                        message=str(fallback_result.error),
                        retryable=False,
                    ) if fallback_result.error else None,
                )
            )

        else:
            # ── Invalid/unsupported document type — safe failure ─────────────────
            logger.warning(f"Document classified as invalid_or_unsupported — failing safely")
            err = ErrorDetail(
                code="UNSUPPORTED_DOCUMENT",
                message=(
                    f"Document could not be classified as a template or filled form. "
                    f"Classification: {role_result.role} (confidence={role_result.confidence:.3f}). "
                    f"Signals: blank={role_result.blank_signals}, filled={role_result.filled_signals}"
                ),
                retryable=False,
            )
            return response_to_dict(build_failure_response(
                request_id=validated.request_id,
                job_id=validated.job_id,
                error=err,
            ))

    logger.info(f"Matched template: {match_result.template_id} (score={match_result.match_score:.3f})")

    # ── Stage 4: Load schema ─────────────────────────────────────────────────
    try:
        schema = registry.load_schema(match_result.template_id)
    except Exception as e:
        logger.error(f"Failed to load schema: {e}")
        err = ErrorDetail(code="TEMPLATE_SCHEMA_LOAD_FAILED", message=str(e), retryable=False)
        return response_to_dict(build_failure_response(
            request_id=validated.request_id,
            job_id=validated.job_id,
            error=err,
        ))

    # ── Stage 5: Extract fields ───────────────────────────────────────────────
    field_results: list[FieldResult] = []

    for field_def in schema.fields:
        result = route_and_extract(
            pdf_path=validated.file.path,
            page_sizes=inspection.page_sizes,
            field_def=field_def,
            glm_available=glm_available,
            gemma_available=gemma_available,
        )

        fr = FieldResult(
            field_name=result.field_name,
            field_label=field_def.get("field_label", ""),
            field_type=field_def.get("field_type", ""),
            value=result.value,
            confidence=result.confidence,
            validation_status=result.validator_status,
            review_required=result.review_required,
            warnings=result.warnings,
            bbox=result.bbox,
        )
        field_results.append(fr)

    # ── Stage 6: Compute document-level confidence ───────────────────────────
    avg_confidence, review_required, low_conf_count = compute_document_confidence(
        field_results, CONFIDENCE_REVIEW_THRESHOLD
    )

    # Override review_required based on any individual field flags
    review_required = (
        review_required
        or any(fr.review_required for fr in field_results)
    )

    warning_count = sum(len(fr.warnings) for fr in field_results)

    summary = Summary(
        template_match_status="matched",
        template_id=match_result.template_id,
        page_count=inspection.page_count,
        overall_confidence=round(avg_confidence, 4),
        review_required=review_required,
        warning_count=warning_count,
        field_count=len(field_results),
    )

    # ── Stage 7: Build response ──────────────────────────────────────────────
    if review_required:
        resp = build_review_required_response(
            request_id=validated.request_id,
            job_id=validated.job_id,
            summary=summary,
            fields=field_results,
        )
    else:
        resp = build_success_response(
            request_id=validated.request_id,
            job_id=validated.job_id,
            summary=summary,
            fields=field_results,
        )

    return response_to_dict(resp)


def main() -> None:
    """Read JSON request from stdin, write JSON response to stdout."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            logger.error("No input received")
            err_resp = {
                "status": "failed",
                "error": {
                    "code": ErrorCode.INVALID_REQUEST,
                    "message": "No input received",
                    "retryable": False,
                },
            }
            sys.stdout.write(json.dumps(err_resp, indent=2) + "\n")
            sys.exit(1)

        data = json.loads(raw)
        result = analyze(data)

        sys.stdout.write(json.dumps(result, indent=2) + "\n")

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON input: {e}")
        err_resp = {
            "status": "failed",
            "error": {
                "code": ErrorCode.INVALID_REQUEST,
                "message": f"Invalid JSON: {e}",
                "retryable": False,
            },
        }
        sys.stdout.write(json.dumps(err_resp, indent=2) + "\n")
        sys.exit(1)
    except RequestValidationError as e:
        logger.error(f"Validation error: {e}")
        err = ErrorDetail(code="INVALID_REQUEST", message=str(e), retryable=False)
        resp = build_failure_response(
            request_id="unknown",
            job_id="unknown",
            error=err,
        )
        sys.stdout.write(json.dumps(response_to_dict(resp), indent=2) + "\n")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        err = ErrorDetail(code="EXTRACTION_FAILED", message=str(e), retryable=True)
        resp = build_failure_response(
            request_id="unknown",
            job_id="unknown",
            error=err,
        )
        sys.stdout.write(json.dumps(response_to_dict(resp), indent=2) + "\n")


if __name__ == "__main__":
    main()