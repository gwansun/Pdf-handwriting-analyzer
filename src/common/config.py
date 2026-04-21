# Configuration for PDF Handwriting Analyzer
#
# All MLX model endpoints and local runtime paths are defined here.
# These should match the SETUP.md specifications.

from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
TEMPLATES_DIR = PROJECT_ROOT / "templates"
CACHE_DIR = PROJECT_ROOT / ".cache"

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
