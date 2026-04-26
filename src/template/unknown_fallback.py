"""Module T7: Unknown Template Fallback

Handles Lane 2b: a filled PDF that has no registered template.
Provisional extraction is attempted and a review_required response is returned.
This module does NOT mutate the template registry.
"""
import logging
from pathlib import Path

from common.config import ErrorCode
from common.types import AnalyzerResponse, ErrorDetail, Summary
from common.response_builder import build_unknown_filled_review_response, response_to_dict
from extractors.provisional_router import extract_provisional_fields, estimate_overall_confidence
from extractors.gemma_client import review_document_extraction
from extractors.gemma_review_pages import render_review_pages
from common.template_registry import TemplateRegistry

logger = logging.getLogger("unknown_fallback")


def extract_unknown_filled_pdf(
    pdf_path: str,
    inspection,
    request_id: str,
    job_id: str,
    registry: TemplateRegistry | None = None,
    glm_available: bool = True,
    gemma_available: bool = True,
) -> dict:
    """
    Lane 2b handler: filled PDF with no registered template.

    Calls provisional extraction (best-effort field detection on unknown
    forms), then returns a review_required response with UNKNOWN_TEMPLATE
    warning. The template registry is NOT mutated.

    If Gemma is available and average document confidence is below threshold,
    one document-level Gemma review pass is invoked using the fallback payload
    (no schema/manifest available).

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.
    inspection : PDFInspectionResult
        Pre-computed inspection result from pdf_inspector.
    request_id : str
        Request identifier (for response).
    job_id : str
        Job identifier (for response).
    registry : TemplateRegistry, optional
        Not used — kept for API symmetry with register_blank_pdf.
    glm_available : bool
        Whether GLM-OCR server is reachable.
    gemma_available : bool
        Whether Gemma server is reachable.

    Returns
    -------
    dict
        AnalyzerResponse serialized to dict, status "review_required".
    """
    from common.config import CONFIDENCE_REVIEW_THRESHOLD
    from common.types import FieldResult

    def _to_field_result(r, review_value=None) -> FieldResult:
        return FieldResult(
            field_name=r.field_name,
            field_label=r.field_name,
            field_type=r.field_type,
            value=r.value,
            confidence=r.confidence,
            validation_status="uncertain",
            review_required=r.confidence < CONFIDENCE_REVIEW_THRESHOLD,
            bbox=r.bbox,
            warnings=r.warnings,
            review=review_value,
        )

    logger.info("Processing unknown filled PDF: %s", pdf_path)

    # Reload registry only if it was mutated during an aborted registration
    # attempt in the same run (no-op here, kept for symmetry).
    if registry is not None:
        try:
            registry.reload()
        except Exception:
            pass  # Best-effort

    try:
        provisional_raw = extract_provisional_fields(
            pdf_path,
            page_sizes=inspection.page_sizes,
            glm_available=glm_available,
        )
        # Convert ProvisionalFieldResult → dicts for Gemma payload
        provisional_results = [
            {
                "field_name": r.field_name,
                "value": r.value,
                "confidence": r.confidence,
                "warnings": r.warnings,
            }
            for r in provisional_raw
        ]
        # Convert to lightweight FieldResult for confidence computation
        provisional_field_results = [_to_field_result(r) for r in provisional_raw]
        overall_confidence = estimate_overall_confidence(provisional_raw)
        field_count = len(provisional_raw)
    except Exception as exc:
        logger.warning("Provisional extraction failed for %s: %s", pdf_path, exc)
        overall_confidence = 0.0
        field_count = 0
        provisional_results = []
        provisional_field_results = []

    # ── Fallback Gemma review with page images ───────────────────────────────
    if provisional_field_results and gemma_available:
        from confidence.scorer import compute_document_confidence
        avg_conf, _, _ = compute_document_confidence(
            provisional_field_results, CONFIDENCE_REVIEW_THRESHOLD
        )
        document_needs_review = any(r.review_required for r in provisional_field_results)
        if document_needs_review:
            logger.info(
                "Fallback path — at least one field is review_required — invoking Gemma fallback review"
            )
            review_target_fields = [
                r.field_name
                for r in provisional_field_results
                if r.review_required
            ]

            # Render all pages (capped) for fallback — no schema so no page selection
            page_numbers = list(range(1, min(inspection.page_count, 5) + 1))
            render_result = render_review_pages(pdf_path, page_numbers)

            review_result = None
            if render_result.error_message is None:
                review_result = review_document_extraction(
                    review_mode="fallback_review",
                    gemma_available=True,
                    document={
                        "page_count": inspection.page_count,
                        "metadata": {},
                    },
                    inspection={
                        "is_born_digital": inspection.is_born_digital,
                        "is_scanned": inspection.is_scanned,
                        "is_hybrid": inspection.is_hybrid,
                        "acroform_field_names": inspection.acroform_field_names or [],
                    },
                    provisional_results=provisional_results,
                    page_images=[
                        {
                            "page_number": page.page_number,
                            "image_url": page.image_url,
                            "mime_type": page.mime_type,
                            "width": page.width,
                            "height": page.height,
                        }
                        for page in render_result.pages
                    ],
                    average_document_confidence=avg_conf,
                    review_target_fields=review_target_fields,
                    warnings=["Template metadata unavailable — fallback review mode"],
                )

            review_failure_message = render_result.error_message or (
                review_result.error_message if review_result else None
            )
            if review_failure_message:
                for r in provisional_field_results:
                    if r.review_required and not r.review_comment:
                        r.review_comment = review_failure_message
                        r.warnings.append(review_failure_message)
            elif review_result is not None:
                review_map = {rf.field_name: rf for rf in review_result.reviewed_fields}
                for r in provisional_field_results:
                    if r.field_name in review_map:
                        rf = review_map[r.field_name]
                        r.review = rf.reviewed_value
                        r.warnings.append(
                            f"Gemma fallback review: '{rf.reasoning}'" if rf.reasoning else "Gemma fallback review applied"
                        )
                        logger.info(
                            f"Gemma fallback reviewed '{r.field_name}': '{r.value}' → '{rf.reviewed_value}'"
                        )
                overall_confidence, _, _ = compute_document_confidence(
                    provisional_field_results, CONFIDENCE_REVIEW_THRESHOLD
                )
    elif provisional_field_results:
        review_unavailable_message = "Gemma whole-document review is unavailable."
        for r in provisional_field_results:
            if r.review_required and not r.review_comment:
                r.review_comment = review_unavailable_message
                r.warnings.append(review_unavailable_message)
    # ── End Fallback Gemma review ────────────────────────────────────────────

    if not provisional_field_results:
        provisional_field_results = [_to_field_result(r) for r in provisional_raw] if 'provisional_raw' in locals() else []

    response = build_unknown_filled_review_response(
        request_id=request_id,
        job_id=job_id,
        page_count=inspection.page_count,
        overall_confidence=overall_confidence,
        field_count=field_count,
        fields=provisional_field_results,
        warnings=[
            {
                "code": "UNKNOWN_TEMPLATE",
                "message": (
                    "No registered template matches this document. "
                    "Provisional extraction performed; results require manual review."
                ),
            },
        ],
    )
    return response_to_dict(response)
