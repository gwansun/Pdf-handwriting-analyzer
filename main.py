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
    response_to_dict,
    ErrorDetail,
)
from extractors.field_router import route_and_extract
from confidence.scorer import compute_document_confidence

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
        logger.info(f"No template match (score={match_result.match_score:.3f})")
        err = ErrorDetail(
            code="UNKNOWN_TEMPLATE",
            message=f"No matching template found (best score={match_result.match_score:.3f})",
            retryable=False,
        )
        return response_to_dict(build_unknown_template_response(
            request_id=validated.request_id,
            job_id=validated.job_id,
            page_count=inspection.page_count,
            error_detail=err,
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