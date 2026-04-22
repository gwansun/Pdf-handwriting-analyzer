"""
Module T2: Registration Types
Typed dataclasses for the blank-PDF template registration workflow.
Keeps registration-specific state out of the analyzer response types.
"""

from dataclasses import dataclass, field
from typing import Optional


# ─── Artifact containers ────────────────────────────────────────────────────────

@dataclass
class GeneratedTemplateArtifacts:
    """Artifacts generated during blank-PDF template registration."""
    manifest_path: Optional[str] = None
    schema_path: Optional[str] = None
    blank_pdf_path: Optional[str] = None
    anchors_path: Optional[str] = None
    debug_assets: dict = field(default_factory=dict)  # optional debug renders


@dataclass
class TemplateIdentity:
    """Identity fields for a newly registered template."""
    template_id: str
    template_family: str
    template_version: str = "1.0"
    display_name: str = ""


# ─── Registration result ────────────────────────────────────────────────────────

@dataclass
class ArtifactWriteResult:
    """Result of writing a single artifact to disk."""
    path: str
    success: bool
    error: Optional[str] = None


@dataclass
class RegistrationResult:
    """
    Result of a full blank-PDF template registration workflow.

    Attributes
    ----------
    success : bool
        Whether registration completed without fatal errors.
    template_id : str or None
        Assigned template ID. None if registration failed.
    template_folder : str or None
        Absolute path to the template folder. None if registration failed.
    artifacts : GeneratedTemplateArtifacts
        Paths to generated artifacts.
    activation_status : str
        One of: "draft", "active", "error".
    warnings : list[str]
        Non-fatal issues encountered during registration.
    errors : list[str]
        Fatal errors that caused registration to fail.
    identity : TemplateIdentity or None
        Assigned template identity fields.
    """
    success: bool
    template_id: Optional[str] = None
    template_folder: Optional[str] = None
    artifacts: GeneratedTemplateArtifacts = field(default_factory=GeneratedTemplateArtifacts)
    activation_status: str = "error"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    identity: Optional[TemplateIdentity] = None


# ─── Fallback result ───────────────────────────────────────────────────────────

@dataclass
class UnknownFallbackResult:
    """
    Result of provisional extraction for an unknown filled PDF.

    Attributes
    ----------
    success : bool
        Whether the fallback extraction ran without a fatal crash.
    field_count : int
        Number of fields extracted (may be 0).
    overall_confidence : float
        Overall confidence score (0.0–1.0), deliberately conservative.
    review_required : bool
        Always True for fallback extraction.
    template_match_status : str
        Always "unknown" for fallback.
    template_id : None
        Always None for fallback.
    warnings : list[dict]
        Warning objects with `code` and `message`.
    error : str or None
        Error message if fallback extraction itself crashed.
    """
    success: bool
    field_count: int = 0
    overall_confidence: float = 0.0
    review_required: bool = True
    template_match_status: str = "unknown"
    template_id: None = None
    warnings: list[dict] = field(default_factory=list)
    error: Optional[str] = None
