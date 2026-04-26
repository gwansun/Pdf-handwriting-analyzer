#!/usr/bin/env python3
"""
PDF Handwriting Analyzer — CLI entry point.
Reads AnalyzerRequest JSON from stdin, writes AnalyzerResponse JSON to stdout.
"""
import json
import logging
import os
import sys
from pathlib import Path


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).parent.resolve()


# Ensure src/ is on path for source execution; frozen builds bundle modules directly.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(_runtime_root() / "src"))

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
from extractors.gemma_client import review_document_extraction
from extractors.gemma_review_pages import (
    select_relevant_review_pages,
    render_review_pages,
    render_review_field_crops,
)
from confidence.scorer import compute_document_confidence
from template.document_role_classifier import classify_document_role, DocumentRole
from template.registration import register_blank_pdf
from template.unknown_fallback import extract_unknown_filled_pdf
from template.registry_api_helpers import (
    normalize_template_list,
    normalize_template_detail,
    normalize_registration_result,
    error_not_found,
    error_invalid_request,
    error_invalid_action,
    error_internal,
)

# ─── Logging ─────────────────────────────────────────────────────────────────

LOG_DIR = Path(os.getenv("PDF_ANALYZER_LOG_DIR", _runtime_root() / "logs")).resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)

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
    """Check if a Gemma-capable server is reachable."""
    try:
        import httpx
        endpoints = [GEMMA_ENDPOINT]
        if GLM_OCR_ENDPOINT not in endpoints:
            endpoints.append(GLM_OCR_ENDPOINT)
        with httpx.Client(timeout=5) as client:
            for endpoint in endpoints:
                try:
                    resp = client.get(f"{endpoint}/v1/models")
                    if resp.status_code == 200:
                        return True
                except Exception:
                    continue
            return False
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
                        request_id=validated.request_id,
                        job_id=validated.job_id,
                        glm_available=glm_available,
                        gemma_available=gemma_available,
                    )
                    return fallback_result
            else:
                # Registration failed — fall back to provisional extraction
                logger.error(
                    f"Template auto-registration failed: errors={reg_result.errors}"
                )
                fallback_result = extract_unknown_filled_pdf(
                    pdf_path=validated.file.path,
                    inspection=inspection,
                    request_id=validated.request_id,
                    job_id=validated.job_id,
                    glm_available=glm_available,
                    gemma_available=gemma_available,
                )
                return fallback_result

        elif role_result.role == DocumentRole.FILLED_INSTANCE:
            # ── Lane 3: Filled PDF, no template match → provisional extraction ──
            logger.info(f"Unknown filled PDF — using provisional fallback extraction")
            fallback_result = extract_unknown_filled_pdf(
                pdf_path=validated.file.path,
                inspection=inspection,
                request_id=validated.request_id,
                job_id=validated.job_id,
                glm_available=glm_available,
                gemma_available=gemma_available,
            )
            return fallback_result

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
            review=None,  # populated by Gemma review below if triggered
            review_comment=None,
        )
        field_results.append(fr)

    # ── Stage 5.5: Document-level Gemma review ─────────────────────────────
    avg_confidence, _review_required, _low_conf_count = compute_document_confidence(
        field_results, CONFIDENCE_REVIEW_THRESHOLD
    )
    document_needs_review = any(fr.review_required for fr in field_results)

    if document_needs_review and gemma_available:
        logger.info(
            "At least one field is review_required — invoking Gemma whole-PDF review"
        )

        all_schema_fields = [
            {
                "field_name": f.get("field_name", ""),
                "field_label": f.get("field_label", ""),
                "field_type": f.get("field_type", ""),
                "page_number": f.get("page_number", 1),
                "bbox": f.get("bbox", []),
            }
            for f in schema.fields
        ]

        review_target_fields = [
            fr.field_name
            for fr in field_results
            if fr.review_required
        ]
        review_target_set = set(review_target_fields)

        schema_fields = [
            f for f in all_schema_fields
            if f.get("field_name") in review_target_set
        ]

        # Build first-pass results for Gemma payload using only review targets.
        first_pass_results = [
            {
                "field_name": fr.field_name,
                "field_label": fr.field_label,
                "field_type": fr.field_type,
                "value": fr.value,
                "confidence": fr.confidence,
                "review_required": fr.review_required,
                "warnings": fr.warnings,
                "bbox": fr.bbox,
            }
            for fr in field_results
            if fr.field_name in review_target_set
        ]

        review_pages, page_selection_warnings = select_relevant_review_pages(
            all_schema_fields,
            review_target_fields,
        )
        render_result = render_review_pages(validated.file.path, review_pages)
        field_crop_result = render_review_field_crops(
            validated.file.path,
            schema_fields,
            review_target_fields,
            inspection.page_sizes,
        )

        # Load manifest for matched-template context
        manifest = registry.get_manifest(match_result.template_id)

        page_images_payload = [
            {
                "page_number": page.page_number,
                "image_url": page.image_url,
                "mime_type": page.mime_type,
                "width": page.width,
                "height": page.height,
            }
            for page in render_result.pages
        ]
        field_images_payload = [
            {
                "field_name": crop.field_name,
                "field_label": crop.field_label,
                "page_number": crop.page_number,
                "image_url": crop.image_url,
                "mime_type": crop.mime_type,
                "width": crop.width,
                "height": crop.height,
            }
            for crop in field_crop_result.field_crops
        ]

        review_result = None
        if render_result.error_message is None:
            review_result = review_document_extraction(
                review_mode="matched_template_review",
                gemma_available=True,
                template={
                    "template_id": match_result.template_id,
                    "template_family": manifest.get("template_family", ""),
                    "display_name": manifest.get("display_name", ""),
                    "template_version": manifest.get("template_version", ""),
                    "runtime_hints": manifest.get("runtime_hints", {}),
                },
                schema_fields=schema_fields,
                first_pass_results=first_pass_results,
                page_images=page_images_payload,
                field_images=field_images_payload,
                average_document_confidence=avg_confidence,
            )

            # Pre-compute once; used for both general-review filter and focused-name
            # skip logic below.
            _first_pass_by_name = {r.get("field_name"): r for r in first_pass_results}

            # Exclude First/Last name from general review when their first-pass
            # confidence is already high (>= 0.75).  The focused-name review
            # (below) handles those fields at the right crop/prompt combination.
            # Sending them to the general review risks Gemma reading them worse
            # than GLM's clean first-pass extraction (e.g. 'Gwanjin' -> 'Guanin').
            _general_review_targets = [
                f for f in review_target_fields
                if f not in ("First_Name_Fill", "Last_Name_Fill", "Name_Employee_Fill")
                or (_first_pass_by_name.get(f) or {}).get("confidence", 1.0) < 0.75
            ]

            _ = review_document_extraction(
                review_mode="matched_template_review",
                gemma_available=True,
                template={
                    "template_id": match_result.template_id,
                    "template_family": manifest.get("template_family", ""),
                    "display_name": manifest.get("display_name", ""),
                    "template_version": manifest.get("template_version", ""),
                    "runtime_hints": manifest.get("runtime_hints", {}),
                },
                schema_fields=schema_fields,
                first_pass_results=first_pass_results,
                page_images=page_images_payload,
                field_images=field_images_payload,
                average_document_confidence=avg_confidence,
                review_target_fields=_general_review_targets,
            )

            # Regression is already avoided for high-confidence name fields by only
            # sending them to the general review when confidence < 0.75.
            focused_name_field_names = [
                name for name in ["First_Name_Fill", "Last_Name_Fill"]
                if name in review_target_set
                and (_first_pass_by_name.get(name) or {}).get("confidence", 1.0) < 0.75
            ]
            # Initialise general_review_map here so the fallback derivation (below)
            # can run independently of whether focused name review ran.
            general_review_map: dict = {
                item.field_name: item for item in (review_result.reviewed_fields if review_result else [])
            }
            if focused_name_field_names:
                focused_name_set = set(focused_name_field_names)
                name_schema_fields = [
                    f for f in schema_fields
                    if f.get("field_name") in focused_name_set
                ]
                name_first_pass_results = [
                    item for item in first_pass_results
                    if item.get("field_name") in focused_name_set
                ]
                name_page_numbers = {f.get("page_number") for f in name_schema_fields}
                name_page_images = [
                    img for img in page_images_payload
                    if img.get("page_number") in name_page_numbers
                ]
                name_field_images = [
                    img for img in field_images_payload
                    if img.get("field_name") in focused_name_set
                ]
                name_review_result = review_document_extraction(
                    review_mode="matched_template_review",
                    gemma_available=True,
                    template={
                        "template_id": match_result.template_id,
                        "template_family": manifest.get("template_family", ""),
                        "display_name": manifest.get("display_name", ""),
                        "template_version": manifest.get("template_version", ""),
                        "runtime_hints": manifest.get("runtime_hints", {}),
                    },
                    schema_fields=name_schema_fields,
                    first_pass_results=name_first_pass_results,
                    page_images=name_page_images,
                    field_images=name_field_images,
                    average_document_confidence=avg_confidence,
                    review_target_fields=focused_name_field_names,
                )
                if name_review_result.reviewed_fields:
                    general_review_map = {
                        item.field_name: item for item in (review_result.reviewed_fields if review_result else [])
                    }
                    for item in name_review_result.reviewed_fields:
                        general_review_map[item.field_name] = item

                    first_name_review = general_review_map.get("First_Name_Fill")
                    last_name_review = general_review_map.get("Last_Name_Fill")
                    if "Name_Employee_Fill" in review_target_set and first_name_review and last_name_review:
                        declaration_full_name = f"{last_name_review.reviewed_value} {first_name_review.reviewed_value}".strip()
                        if declaration_full_name:
                            from extractors.gemma_client import ReviewedField
                            general_review_map["Name_Employee_Fill"] = ReviewedField(
                                field_name="Name_Employee_Fill",
                                reviewed_value=declaration_full_name,
                                reviewed_confidence=min(
                                    value for value in [
                                        first_name_review.reviewed_confidence,
                                        last_name_review.reviewed_confidence,
                                    ] if value is not None
                                ) if any(
                                    value is not None for value in [
                                        first_name_review.reviewed_confidence,
                                        last_name_review.reviewed_confidence,
                                    ]
                                ) else None,
                                reasoning="Derived from the focused first-name and last-name Gemma review outputs.",
                            )
                    if review_result is None:
                        review_result = name_review_result
                        review_result.reviewed_fields = list(general_review_map.values())
                    else:
                        review_result.reviewed_fields = list(general_review_map.values())

            # Fallback derivation: if Name_Employee_Fill was skipped by first-pass
            # GLM (empty, confidence=0.0) but Gemma didn't review First/Last name
            # fields (because their first-pass confidence >= 0.75), derive from
            # the clean first-pass values directly.  This avoids Gemma crop-read
            # regressions on name fields that GLM already extracted correctly.
            if (
                "Name_Employee_Fill" in review_target_set
                and general_review_map.get("Name_Employee_Fill") is None
            ):
                fp_by_name = {r.field_name: r for r in first_pass_results}
                fn_first = fp_by_name.get("First_Name_Fill")
                fn_last = fp_by_name.get("Last_Name_Fill")
                if fn_first and fn_last:
                    derived_value = f"{fn_last.get('value', '')} {fn_first.get('value', '')}".strip()
                    if derived_value:
                        from extractors.gemma_client import ReviewedField
                        _derived = ReviewedField(
                            field_name="Name_Employee_Fill",
                            reviewed_value=derived_value,
                            reviewed_confidence=min(
                                float(fn_first.get('confidence', 0.0)),
                                float(fn_last.get('confidence', 0.0)),
                            ),
                            reasoning="Derived from clean GLM first-pass name extractions (Gemma review skipped — GLM already confident and accurate).",
                        )
                        general_review_map["Name_Employee_Fill"] = _derived
                        if review_result is None:
                            from extractors.gemma_client import GemmaReviewResult
                            review_result = GemmaReviewResult(reviewed_fields=[_derived])
                        else:
                            review_result.reviewed_fields = list(general_review_map.values())

        review_failure_message = render_result.error_message or (
            review_result.error_message if review_result else None
        )
        combined_review_warnings = page_selection_warnings + field_crop_result.warnings
        if combined_review_warnings:
            for fr in field_results:
                if fr.field_name in review_target_fields:
                    fr.warnings.extend(combined_review_warnings)
        if review_failure_message:
            for fr in field_results:
                if fr.field_name in review_target_fields and not fr.review_comment:
                    fr.review_comment = review_failure_message
                    fr.warnings.append(review_failure_message)
        elif review_result is not None:
            review_map = {r.field_name: r for r in review_result.reviewed_fields}
            for fr in field_results:
                if fr.field_name in review_map:
                    rf = review_map[fr.field_name]
                    fr.review = rf.reviewed_value
                    fr.review_comment = rf.reasoning
                    logger.info(
                        f"Gemma reviewed '{fr.field_name}': '{fr.value}' → '{rf.reviewed_value}'"
                    )
    elif document_needs_review:
        review_unavailable_message = "Gemma whole-document review is unavailable."
        for fr in field_results:
            if fr.review_required and not fr.review_comment:
                fr.review_comment = review_unavailable_message
                fr.warnings.append(review_unavailable_message)

    # ── Stage 6: Compute document-level confidence ───────────────────────────
    avg_confidence, _review_required, low_conf_count = compute_document_confidence(
        field_results, CONFIDENCE_REVIEW_THRESHOLD
    )
    review_required = any(fr.review_required for fr in field_results)

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

        # ── Action envelope dispatch ──────────────────────────────────────
        action = data.get("action")
        if action is not None:
            result = _dispatch_registry_action(action, data)
            sys.stdout.write(json.dumps(result, indent=2) + "\n")
            return

        # Default: PDF analysis path
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


# ---------------------------------------------------------------------------
# Registry action dispatch
# ---------------------------------------------------------------------------

SUPPORTED_ACTIONS = {"list_templates", "get_template_detail", "register_template"}


def _dispatch_registry_action(action: str, data: dict) -> dict:
    """
    Dispatch a registry action and return a JSON-serializable dict.

    All exceptions are caught here and converted to structured error responses
    so no raw tracebacks escape to stdout.
    """
    try:
        if action == "list_templates":
            return _handle_list_templates()
        elif action == "get_template_detail":
            return _handle_get_template_detail(data)
        elif action == "register_template":
            return _handle_register_template(data)
        else:
            return error_invalid_action(action)
    except Exception as exc:
        logger.exception(f"Error handling action '{action}': {exc}")
        return error_internal(str(exc), action)


def _handle_list_templates() -> dict:
    """``action: list_templates`` — return all active templates."""
    registry = TemplateRegistry()
    return normalize_template_list(registry)


def _handle_get_template_detail(data: dict) -> dict:
    """``action: get_template_detail`` — return one template or not-found."""
    template_id = data.get("template_id")
    if not template_id:
        return error_invalid_request("template_id is required", "get_template_detail")

    registry = TemplateRegistry()
    result = normalize_template_detail(registry, template_id)
    if result is None:
        return error_not_found(f"Template '{template_id}' not found", "get_template_detail")
    return result


def _handle_register_template(data: dict) -> dict:
    """
    ``action: register_template`` — inspect and register a blank PDF.

    Request fields
    -------------
    file_path : str  (required, absolute path)
    template_family_hint : str | None  (optional)
    activate : bool  (optional, default False)
    """
    file_path = data.get("file_path")
    if not file_path:
        return _registration_failure_response(
            "file_path is required",
            ["file_path is required"],
        )

    # Reject relative paths — only absolute paths are accepted
    if not Path(file_path).is_absolute():
        return _registration_failure_response(
            f"file_path must be absolute, got relative: {file_path}",
            [f"Relative paths are not allowed: {file_path}"],
        )

    path = Path(file_path).resolve()
    if not path.exists() or not path.is_file():
        return _registration_failure_response(
            f"File not found or not a file: {file_path}",
            [f"File not found: {file_path}"],
        )

    # Run PDF inspection
    try:
        inspection = inspect_pdf(str(path))
    except PDFInspectionError as exc:
        return _registration_failure_response(
            f"PDF inspection failed: {exc.message}",
            [f"Failed to inspect PDF: {exc.message}"],
        )
    except Exception as exc:
        return _registration_failure_response(
            f"PDF inspection failed: {exc}",
            [f"Failed to inspect PDF: {exc}"],
        )

    # Template family hint
    template_family_hint = data.get("template_family_hint")
    activate = bool(data.get("activate", False))

    # Run registration
    try:
        reg_result = register_blank_pdf(
            pdf_path=str(path),
            inspection=inspection,
            template_family_hint=template_family_hint,
            templates_dir=None,
            activate=activate,
        )
    except Exception as exc:
        logger.exception(f"Registration failed: {exc}")
        return _registration_failure_response(
            str(exc),
            [f"Registration failed: {exc}"],
        )

    return normalize_registration_result(reg_result)


def _registration_failure_response(message: str, errors: list[str]) -> dict:
    """Build a registration-failure response in the standard shape."""
    return {
        "action": "register_template",
        "success": False,
        "template_id": None,
        "template_folder": None,
        "activation_status": "error",
        "artifacts": {
            "blank_pdf_path": None,
            "manifest_path": None,
            "schema_path": None,
        },
        "warnings": [],
        "errors": errors,
    }


if __name__ == "__main__":
    main()