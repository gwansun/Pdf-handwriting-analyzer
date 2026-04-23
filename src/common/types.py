# Common data models / request-response types
# These are kept separate from any specific module to avoid circular imports.

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileInfo:
    path: str
    original_filename: Optional[str] = None
    saved_filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None


@dataclass
class EmailContext:
    received_date: Optional[str] = None  # YYYY-MM-DD
    sender: Optional[str] = None
    subject: Optional[str] = None
    language_hint: Optional[str] = "en"
    template_hint: Optional[str] = None


@dataclass
class RequestOptions:
    return_field_candidates: bool = False
    return_confidence_breakdown: bool = False
    mode: str = "default"


@dataclass
class AnalyzerRequest:
    request_id: str
    job_id: str
    attachment_id: str
    file: FileInfo
    email_id: Optional[str] = None
    context: Optional[EmailContext] = None
    options: Optional[RequestOptions] = None


@dataclass
class ReviewedField:
    """Output from a Gemma whole-PDF review pass for a single field."""
    field_name: str
    reviewed_value: str
    reviewed_confidence: Optional[float] = None
    reasoning: Optional[str] = None


@dataclass
class FieldResult:
    field_name: str
    field_label: str
    field_type: str
    value: Optional[str] = None
    confidence: float = 0.0
    validation_status: str = "valid"  # valid | uncertain | invalid
    review_required: bool = False
    warnings: list = field(default_factory=list)
    bbox: list = field(default_factory=list)  # [x0, y0, x1, y1]
    # Gemma review output — attached separately; never overwrites value/confidence
    review: Optional[str] = None


@dataclass
class Summary:
    template_match_status: str = "unknown"  # matched | unknown
    template_id: Optional[str] = None
    page_count: int = 0
    overall_confidence: float = 0.0
    review_required: bool = False
    warning_count: int = 0
    field_count: int = 0


@dataclass
class ErrorDetail:
    code: str
    message: str
    retryable: bool = False


@dataclass
class AnalyzerResponse:
    request_id: str
    job_id: str
    status: str  # completed | review_required | failed
    summary: Optional[Summary] = None
    fields: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    error: Optional[ErrorDetail] = None
