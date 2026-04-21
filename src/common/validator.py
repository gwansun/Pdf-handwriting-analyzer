"""
Module A: Request Validator
Validates incoming JSON requests against the frozen MVP contract.
Returns a normalized AnalyzerRequest or a contract-compliant failure response.
"""

import json
import os
from pathlib import Path
from typing import Optional

from .types import AnalyzerRequest, EmailContext, ErrorDetail, FileInfo, RequestOptions
from .config import ErrorCode


class RequestValidationError(Exception):
    """Raised when request validation fails. Carries the error detail."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)

    def to_error_detail(self) -> ErrorDetail:
        return ErrorDetail(code=self.code, message=self.message, retryable=self.retryable)


def validate_json_request(raw: dict) -> AnalyzerRequest:
    """
    Validate a raw JSON request dict against the frozen MVP contract.

    Raises RequestValidationError with structured error detail if validation fails.
    Returns a fully-typed AnalyzerRequest on success.
    """
    # ── Required top-level fields ────────────────────────────────────────────

    request_id = _get_required_str(raw, "request_id")
    job_id = _get_required_str(raw, "job_id")
    attachment_id = _get_required_str(raw, "attachment_id")

    # ── File section ─────────────────────────────────────────────────────────

    file_section = _get_required_dict(raw, "file")
    file_path = _get_required_str(file_section, "path")

    # ── File existence and readability ───────────────────────────────────────

    if not os.path.exists(file_path):
        raise RequestValidationError(
            ErrorCode.FILE_NOT_FOUND,
            f"File not found: {file_path}",
            retryable=False,
        )

    if not os.access(file_path, os.R_OK):
        raise RequestValidationError(
            ErrorCode.UNREADABLE_FILE,
            f"File is not readable: {file_path}",
            retryable=False,
        )

    # ── Basic MIME type / extension check ────────────────────────────────────

    if not _is_pdf_path(file_path):
        raise RequestValidationError(
            ErrorCode.NOT_A_PDF,
            f"File does not appear to be a PDF (check extension): {file_path}",
            retryable=False,
        )

    # ── Optional file metadata ───────────────────────────────────────────────

    file_info = FileInfo(
        path=file_path,
        original_filename=file_section.get("original_filename"),
        saved_filename=file_section.get("saved_filename"),
        mime_type=file_section.get("mime_type"),
        size_bytes=_get_int_or_none(file_section, "size_bytes"),
        checksum=file_section.get("checksum"),
    )

    # ── Optional top-level fields ────────────────────────────────────────────

    email_id = raw.get("email_id")

    # ── Context section ───────────────────────────────────────────────────────

    context_raw = raw.get("context")
    context = None
    if context_raw:
        context = EmailContext(
            received_date=context_raw.get("received_date"),
            sender=context_raw.get("sender"),
            subject=context_raw.get("subject"),
            language_hint=context_raw.get("language_hint", "en"),
            template_hint=context_raw.get("template_hint"),
        )

    # ── Options section ───────────────────────────────────────────────────────

    options_raw = raw.get("options")
    options = None
    if options_raw:
        options = RequestOptions(
            return_field_candidates=bool(options_raw.get("return_field_candidates", False)),
            return_confidence_breakdown=bool(options_raw.get("return_confidence_breakdown", False)),
            mode=str(options_raw.get("mode", "default")),
        )

    return AnalyzerRequest(
        request_id=request_id,
        job_id=job_id,
        attachment_id=attachment_id,
        file=file_info,
        email_id=email_id,
        context=context,
        options=options,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

_REQUIRED_STRING_FIELDS = ["request_id", "job_id", "attachment_id"]


def _get_required_str(data: dict, key: str) -> str:
    val = data.get(key)
    if val is None:
        raise RequestValidationError(
            ErrorCode.INVALID_REQUEST,
            f"Missing required field: '{key}'",
            retryable=False,
        )
    if not isinstance(val, str):
        raise RequestValidationError(
            ErrorCode.INVALID_REQUEST,
            f"Field '{key}' must be a string, got {type(val).__name__}",
            retryable=False,
        )
    return val


def _get_required_dict(data: dict, key: str) -> dict:
    val = data.get(key)
    if val is None:
        raise RequestValidationError(
            ErrorCode.INVALID_REQUEST,
            f"Missing required field: '{key}'",
            retryable=False,
        )
    if not isinstance(val, dict):
        raise RequestValidationError(
            ErrorCode.INVALID_REQUEST,
            f"Field '{key}' must be an object, got {type(val).__name__}",
            retryable=False,
        )
    return val


def _get_int_or_none(data: dict, key: str) -> Optional[int]:
    val = data.get(key)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        raise RequestValidationError(
            ErrorCode.INVALID_REQUEST,
            f"Field '{key}' must be an integer, got {type(val).__name__}",
            retryable=False,
        )


def _is_pdf_path(path: str) -> bool:
    """Check file extension only — actual PDF validation happens in PDF inspector."""
    return Path(path).suffix.lower() in (".pdf", ".PDF")
