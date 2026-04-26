# Configuration for PDF Handwriting Analyzer
#
# All MLX model endpoints and local runtime paths are defined here.
# These should match the SETUP.md specifications.

import os
import sys
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

def _default_project_root() -> Path:
    """Resolve a stable writable root for source and frozen builds."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).parent.parent.parent.resolve()


def _bundled_asset_root() -> Path:
    """Resolve the location of bundled read-only assets in frozen builds."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()
    return _default_project_root()


def _default_templates_dir() -> Path:
    """Templates live under the source tree or the PyInstaller bundle asset root."""
    if getattr(sys, "frozen", False):
        return _bundled_asset_root() / "templates"
    return _default_project_root() / "templates"


PROJECT_ROOT = Path(os.getenv("PDF_ANALYZER_PROJECT_ROOT", _default_project_root())).resolve()
TEMPLATES_DIR = Path(os.getenv("PDF_ANALYZER_TEMPLATES_DIR", _default_templates_dir())).resolve()
CACHE_DIR = Path(os.getenv("PDF_ANALYZER_CACHE_DIR", PROJECT_ROOT / ".cache")).resolve()
REVIEW_PAGE_IMAGE_DIR = Path(
    os.getenv("PDF_ANALYZER_REVIEW_PAGE_IMAGE_DIR", PROJECT_ROOT / "logs" / "review_pages")
).resolve()

# ─── MLX Model Endpoints ───────────────────────────────────────────────────────

# Primary handwriting extraction: GLM-OCR served via mlx-vlm.server
GLM_OCR_ENDPOINT = "http://127.0.0.1:11436"

# Review/refine model: Gemma 4 E4B served via mlx_lm server
GEMMA_ENDPOINT = "http://127.0.0.1:11435"

# ─── Timeout settings ─────────────────────────────────────────────────────────

# Seconds to wait for a model response before giving up
MODEL_TIMEOUT_SECONDS = 120

# ─── Confidence thresholds ────────────────────────────────────────────────────

# Fields below this confidence trigger review_required status
CONFIDENCE_REVIEW_THRESHOLD = 0.70

# Confidence below this causes automatic Gemma review/refine for handwritten
CONFIDENCE_GEMMA_REVIEW_THRESHOLD = 0.70

# ─── Template matching ─────────────────────────────────────────────────────────

# Scores >= this threshold are considered a matched template
TEMPLATE_MATCH_THRESHOLD = 0.85

# Scores in this range are considered provisional (not used in MVP)
TEMPLATE_PROVISIONAL_MIN = 0.65
TEMPLATE_PROVISIONAL_MAX = 0.84

# ─── Artifact retention ─────────────────────────────────────────────────────────

# Persist debug artifacts (crops, overlays) only in debug mode or on failure/review
ARTIFACT_RETENTION_MODES = {"debug", "failure", "review_required"}

# ─── Error codes ──────────────────────────────────────────────────────────────

class ErrorCode:
    INVALID_REQUEST = "INVALID_REQUEST"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    UNREADABLE_FILE = "UNREADABLE_FILE"
    NOT_A_PDF = "NOT_A_PDF"
    UNSUPPORTED_ENCRYPTION = "UNSUPPORTED_ENCRYPTION"
    UNKNOWN_TEMPLATE = "UNKNOWN_TEMPLATE"
    TEMPLATE_SCHEMA_LOAD_FAILED = "TEMPLATE_SCHEMA_LOAD_FAILED"
    ALIGNMENT_FAILED = "ALIGNMENT_FAILED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    MODEL_CALL_FAILED = "MODEL_CALL_FAILED"
