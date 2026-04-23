"""
Registry API helpers — normalize Python objects into JSON-serializable dicts
for the Email Manager subprocess CLI boundary.

Provides:
- list_templates response normalization
- get_template_detail response normalization
- register_template response normalization
- standard error helpers
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from common.template_registry import TemplateRegistry
from common.config import TEMPLATES_DIR

logger = logging.getLogger("registry_api_helpers")

# ---------------------------------------------------------------------------
# Template list normalization
# ---------------------------------------------------------------------------

def normalize_template_list(registry: TemplateRegistry) -> dict[str, Any]:
    """
    Build the ``list_templates`` action response from the live registry.

    Returns
    -------
    dict
        ``{"action": "list_templates", "templates": [...], "count": N}``
    """
    records = registry.list_active()
    rows = []
    for rec in records:
        try:
            # field_count requires loading schema.json
            schema_data = _load_schema_data(rec.template_id)
            schema_fields = schema_data.get("fields", [])
            field_count = len(schema_fields) if isinstance(schema_fields, list) else 0
            blank_available = _blank_pdf_available(rec.template_id)
            rows.append({
                "template_id": rec.template_id,
                "display_name": rec.display_name,
                "template_family": rec.template_family,
                "template_version": rec.template_version,
                "status": rec.status,
                "created_at": _safeIsoDate(rec.created_at),
                "updated_at": _safeIsoDate(rec.updated_at),
                "field_count": field_count,
                "blank_pdf_available": blank_available,
            })
        except Exception as exc:
            logger.warning("Skipping template %s during list normalization: %s", rec.template_id, exc)
            continue

    return {
        "action": "list_templates",
        "templates": rows,
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# Template detail normalization
# ---------------------------------------------------------------------------

def normalize_template_detail(
    registry: TemplateRegistry,
    template_id: str,
) -> dict[str, Any] | None:
    """
    Build the ``get_template_detail`` action response for one template.

    Returns None when the template does not exist.
    """
    rec = registry.get(template_id)
    if rec is None:
        return None

    schema_data = _load_schema_data(template_id)
    schema_fields = schema_data.get("fields", [])
    field_count = len(schema_fields) if isinstance(schema_fields, list) else 0

    blank_available = _blank_pdf_available(template_id)

    # Template-relative artifact paths (not absolute filesystem paths)
    template_folder = f"templates/{template_id}"

    return {
        "action": "get_template_detail",
        "template_id": rec.template_id,
        "display_name": rec.display_name,
        "template_family": rec.template_family,
        "template_version": rec.template_version,
        "status": rec.status,
        "created_at": _safeIsoDate(rec.created_at),
        "updated_at": _safeIsoDate(rec.updated_at),
        "runtime_hints": _runtime_hints_with_defaults(rec.runtime_hints),
        "artifacts": {
            "manifest_path": f"{template_folder}/manifest.json",
            "schema_path": f"{template_folder}/schema.json",
            "blank_pdf_available": blank_available,
        },
        "schema": {
            "field_count": field_count,
            "fields": schema_fields,
        },
    }


# ---------------------------------------------------------------------------
# Registration response normalization
# ---------------------------------------------------------------------------

def normalize_registration_result(result: Any) -> dict[str, Any]:
    """
    Convert a RegistrationResult (or duck-typed object) into the
    ``register_template`` action response shape.
    """
    success = getattr(result, "success", False)
    template_id = getattr(result, "template_id", None)
    artifacts_obj = getattr(result, "artifacts", None)

    if artifacts_obj:
        artifacts = {
            "blank_pdf_path": _relative_path(getattr(artifacts_obj, "blank_pdf_path", None)),
            "manifest_path": _relative_path(getattr(artifacts_obj, "manifest_path", None)),
            "schema_path": _relative_path(getattr(artifacts_obj, "schema_path", None)),
        }
        activation_status = getattr(result, "activation_status", "draft" if success else "error")
        template_folder = getattr(result, "template_folder", None)
    else:
        artifacts = {
            "blank_pdf_path": None,
            "manifest_path": None,
            "schema_path": None,
        }
        activation_status = "draft" if success else "error"
        template_folder = None

    warnings = list(getattr(result, "warnings", []) or [])
    errors = list(getattr(result, "errors", []) or [])

    return {
        "action": "register_template",
        "success": success,
        "template_id": template_id,
        "template_folder": template_folder,
        "activation_status": activation_status,
        "artifacts": artifacts,
        "warnings": warnings,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Standard error helpers
# ---------------------------------------------------------------------------

def error_not_found(message: str, action: str = "") -> dict[str, Any]:
    return {
        "action": action,
        "error": {
            "code": "TEMPLATE_NOT_FOUND",
            "message": message,
        },
    }


def error_invalid_request(message: str, action: str = "") -> dict[str, Any]:
    return {
        "action": action,
        "error": {
            "code": "INVALID_REQUEST",
            "message": message,
        },
    }


def error_invalid_action(action: str) -> dict[str, Any]:
    return {
        "action": action or "<unknown>",
        "error": {
            "code": "INVALID_ACTION",
            "message": f"Unknown action: '{action}'",
        },
    }


def error_internal(message: str, action: str = "") -> dict[str, Any]:
    return {
        "action": action,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": message,
        },
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_field_count(template_id: str) -> int:
    """Load schema.json and return the number of fields, or 0 on failure."""
    schema_path = TEMPLATES_DIR / template_id / "schema.json"
    if not schema_path.exists():
        return 0
    try:
        import json
        with schema_path.open() as fh:
            data = json.load(fh)
        fields = data.get("fields", [])
        return len(fields) if isinstance(fields, list) else 0
    except Exception:
        return 0


def _blank_pdf_available(template_id: str) -> bool:
    """True when the blank PDF copy exists inside the template folder."""
    folder = TEMPLATES_DIR / template_id
    # Try common naming patterns
    for candidate in (f"{template_id}.pdf", "blank.pdf", "template.pdf"):
        if (folder / candidate).exists():
            return True
    return False


def _load_schema_data(template_id: str) -> dict:
    """Load and return schema.json contents as a dict."""
    schema_path = TEMPLATES_DIR / template_id / "schema.json"
    if not schema_path.exists():
        return {"field_count": 0, "fields": []}
    try:
        import json
        with schema_path.open() as fh:
            return json.load(fh)
    except Exception:
        return {"field_count": 0, "fields": []}


def _runtime_hints_with_defaults(hints: Any) -> dict:
    """Fill safe defaults for runtime_hints, which may be a dict or a dataclass."""
    defaults = {
        "default_input_mode": "mixed",
        "primary_language": "en",
        "alignment_mode": "strict",
        "unknown_field_policy": "review",
        "preferred_extractors": [],
    }
    if not hints:
        return defaults
    # Convert dataclass to dict if needed
    if not isinstance(hints, dict):
        hints = _dataclass_to_dict(hints)
    return {**defaults, **hints}


def _dataclass_to_dict(obj: Any) -> dict:
    """Convert a dataclass to a dict recursively."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name, None)
            result[field_name] = _dataclass_to_dict(value) if hasattr(value, "__dataclass_fields__") else value
        return result
    return {}


def _safeIsoDate(value: Any) -> str:
    """Return an ISO-8601 string or empty string for None/malformed dates."""
    if not value:
        return ""
    if isinstance(value, str):
        return value
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _relative_path(absolute_path_str: Optional[str]) -> Optional[str]:
    """
    Convert an absolute path to a template-relative path like 'templates/<id>/...'.
    Returns None if the input is None or not under TEMPLATES_DIR.
    """
    if not absolute_path_str:
        return None
    try:
        p = Path(absolute_path_str).resolve()
        templates = TEMPLATES_DIR.resolve()
        if p.is_relative_to(templates):
            return str(p.relative_to(templates))
        return None
    except Exception:
        return absolute_path_str
