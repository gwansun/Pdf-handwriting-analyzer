"""
Module K: Response Builder
Builds contract-compliant AnalyzerResponse objects from internal pipeline results.
Handles completed, review_required, and failed statuses.
"""

from typing import Any, Optional

from .types import (
    AnalyzerResponse,
    ErrorDetail,
    FieldResult,
    Summary,
)


def build_success_response(
    request_id: str,
    job_id: str,
    summary: Summary,
    fields: list[FieldResult],
    warnings: Optional[list] = None,
) -> AnalyzerResponse:
    """Return a 'completed' response with no errors."""
    return AnalyzerResponse(
        request_id=request_id,
        job_id=job_id,
        status="completed",
        summary=summary,
        fields=fields,
        warnings=warnings or [],
        error=None,
    )


def build_review_required_response(
    request_id: str,
    job_id: str,
    summary: Summary,
    fields: list[FieldResult],
    warnings: Optional[list] = None,
) -> AnalyzerResponse:
    """Return a 'review_required' response — extraction worked but confidence is low."""
    return AnalyzerResponse(
        request_id=request_id,
        job_id=job_id,
        status="review_required",
        summary=summary,
        fields=fields,
        warnings=warnings or [],
        error=None,
    )


def build_failure_response(
    request_id: str,
    job_id: str,
    error: ErrorDetail,
    summary: Optional[Summary] = None,
    warnings: Optional[list] = None,
) -> AnalyzerResponse:
    """Return a 'failed' response with structured error information."""
    return AnalyzerResponse(
        request_id=request_id,
        job_id=job_id,
        status="failed",
        summary=summary,
        fields=[],
        warnings=warnings or [],
        error=error,
    )


def build_unknown_template_response(
    request_id: str,
    job_id: str,
    page_count: int,
    error_detail: ErrorDetail,
) -> AnalyzerResponse:
    """
    Convenience builder for the unknown-template fail-fast response.
    Returns a contract-compliant failed response with summary and warning set.
    """
    summary = Summary(
        template_match_status="unknown",
        template_id=None,
        page_count=page_count,
        overall_confidence=0.0,
        review_required=True,
        warning_count=1,
        field_count=0,
    )
    warnings = [{"code": error_detail.code, "message": error_detail.message}]
    return build_failure_response(
        request_id=request_id,
        job_id=job_id,
        error=error_detail,
        summary=summary,
        warnings=warnings,
    )


def response_to_dict(resp: AnalyzerResponse) -> dict[str, Any]:
    """
    Convert an AnalyzerResponse to a plain dict matching the frozen MVP JSON schema.
    Used for serialization to JSON before returning to Email Manager.
    """
    result: dict[str, Any] = {
        "request_id": resp.request_id,
        "job_id": resp.job_id,
        "status": resp.status,
    }

    if resp.summary is not None:
        result["summary"] = {
            "template_match_status": resp.summary.template_match_status,
            "template_id": resp.summary.template_id,
            "page_count": resp.summary.page_count,
            "overall_confidence": resp.summary.overall_confidence,
            "review_required": resp.summary.review_required,
            "warning_count": resp.summary.warning_count,
            "field_count": resp.summary.field_count,
        }

    if resp.fields is not None:
        result["fields"] = [
            {
                "field_name": f.field_name,
                "field_label": f.field_label,
                "field_type": f.field_type,
                "value": f.value,
                "confidence": f.confidence,
                "validation_status": f.validation_status,
                "review_required": f.review_required,
                "warnings": f.warnings,
                "bbox": f.bbox,
            }
            for f in resp.fields
        ]

    if resp.warnings:
        result["warnings"] = resp.warnings

    if resp.error is not None:
        result["error"] = {
            "code": resp.error.code,
            "message": resp.error.message,
            "retryable": resp.error.retryable,
        }

    return result
