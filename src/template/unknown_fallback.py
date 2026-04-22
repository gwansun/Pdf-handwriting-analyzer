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
from common.template_registry import TemplateRegistry

logger = logging.getLogger("unknown_fallback")


def extract_unknown_filled_pdf(
    pdf_path: str,
    inspection,
    request_id: str,
    job_id: str,
    registry: TemplateRegistry | None = None,
) -> dict:
    """
    Lane 2b handler: filled PDF with no registered template.

    Calls provisional extraction (best-effort field detection on unknown
    forms), then returns a review_required response with UNKNOWN_TEMPLATE
    warning. The template registry is NOT mutated.

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

    Returns
    -------
    dict
        AnalyzerResponse serialized to dict, status "review_required".
    """
    logger.info("Processing unknown filled PDF: %s", pdf_path)

    # Reload registry only if it was mutated during an aborted registration
    # attempt in the same run (no-op here, kept for symmetry).
    if registry is not None:
        try:
            registry.reload()
        except Exception:
            pass  # Best-effort

    try:
        provisional = extract_provisional_fields(pdf_path, inspection)
        overall_confidence = estimate_overall_confidence(provisional, inspection)
        field_count = len(provisional)
    except Exception as exc:
        logger.warning("Provisional extraction failed for %s: %s", pdf_path, exc)
        overall_confidence = 0.0
        field_count = 0

    response = build_unknown_filled_review_response(
        request_id=request_id,
        job_id=job_id,
        page_count=inspection.page_count,
        overall_confidence=overall_confidence,
        field_count=field_count,
        warnings=[{
            "code": "UNKNOWN_TEMPLATE",
            "message": (
                "No registered template matches this document. "
                "Provisional extraction performed; results require manual review."
            ),
        }],
    )
    return response_to_dict(response)
