"""
Module B: PDF Inspector
Opens a PDF, extracts page count, metadata, and detects born-digital vs scanned vs hybrid.
Supports empty-password decryption for encrypted PDFs.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pypdf

from .config import ErrorCode


class PDFInspectionError(Exception):
    """Raised when PDF inspection fails. Carries structured error info."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


@dataclass
class PDFInspectionResult:
    page_count: int
    is_encrypted: bool
    is_born_digital: bool  # True if native PDF text / AcroForm present
    is_scanned: bool       # True if no native text and no AcroForm
    is_hybrid: bool        # True if both native text and image content
    acroform_field_names: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    page_sizes: list[tuple] = field(default_factory=list)  # [(width, height), ...]
    file_path: str = ""


def inspect_pdf(file_path: str) -> PDFInspectionResult:
    """
    Inspect a PDF file and return structured metadata.
    Supports empty-password decryption; raises on encrypted PDFs that need a password.
    """
    try:
        reader = pypdf.PdfReader(file_path, strict=False)
    except FileNotFoundError:
        raise PDFInspectionError(
            ErrorCode.UNREADABLE_FILE,
            f"File not found: {file_path}",
            retryable=False,
        )
    except pypdf.errors.WrongPasswordError:
        raise PDFInspectionError(
            ErrorCode.UNSUPPORTED_ENCRYPTION,
            f"PDF is encrypted and requires a non-empty password: {file_path}",
            retryable=False,
        )
    except Exception as e:
        raise PDFInspectionError(
            ErrorCode.UNREADABLE_FILE,
            f"Failed to open PDF: {e}",
            retryable=False,
        )

    is_encrypted = reader.is_encrypted

    # Try empty-password decrypt if encrypted
    if is_encrypted:
        try:
            reader.decrypt("")
        except pypdf.errors.WrongPasswordError:
            raise PDFInspectionError(
                ErrorCode.UNSUPPORTED_ENCRYPTION,
                f"PDF is encrypted with a non-empty password: {file_path}",
                retryable=False,
            )

    page_count = len(reader.pages)

    # Extract metadata
    metadata = {}
    if reader.metadata:
        metadata = {
            k: str(v) for k, v in (reader.metadata or {}).items() if v is not None
        }

    # Collect page sizes
    page_sizes = []
    for page in reader.pages:
        mediabox = page.mediabox
        page_sizes.append((float(mediabox.width), float(mediabox.height)))

    # Detect AcroForm fields
    acroform_field_names = _extract_acroform_field_names(reader)

    # Detect document type
    has_native_text = _has_native_text(reader)
    has_acroform = len(acroform_field_names) > 0
    has_images = _has_images(reader)

    is_born_digital = has_native_text or has_acroform
    is_hybrid = has_native_text and has_images
    is_scanned = not is_born_digital and has_images

    return PDFInspectionResult(
        page_count=page_count,
        is_encrypted=is_encrypted,
        is_born_digital=is_born_digital,
        is_scanned=is_scanned,
        is_hybrid=is_hybrid,
        acroform_field_names=acroform_field_names,
        metadata=metadata,
        page_sizes=page_sizes,
        file_path=file_path,
    )


def _extract_acroform_field_names(reader: pypdf.PdfReader) -> list[str]:
    """Extract AcroForm field names if present."""
    fields = []
    if reader.get_fields():
        for name, field_obj in reader.get_fields().items():
            if name:
                fields.append(name)
    return fields


def _has_native_text(reader: pypdf.PdfReader) -> bool:
    """Check if any page contains extractable native text."""
    for page in reader.pages:
        text = page.extract_text()
        if text and text.strip():
            return True
    return False


def _has_images(reader: pypdf.PdfReader) -> bool:
    """Check if any page contains image XObjects."""
    for page in reader.pages:
        if "/XObject" in page:
            xobj = page["/XObject"]
            if isinstance(xobj, pypdf.objects.DictionaryObject):
                for key in xobj:
                    if xobj[key].get("/Subtype") == "/Image":
                        return True
    return False
