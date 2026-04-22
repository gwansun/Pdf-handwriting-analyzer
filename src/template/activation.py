"""
Module T6: Activation
Handles template post-registration lifecycle — draft validation,
promotion to active, and registry cache management.

All auto-generated templates start as draft. Activation is a separate
lifecycle step that can be triggered manually after review.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from common.config import TEMPLATES_DIR, ErrorCode
from common.template_registry import TemplateRegistry

logger = logging.getLogger("activation")


class ActivationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _load_manifest(template_folder: Path) -> Optional[dict]:
    """Load manifest.json from a template folder."""
    manifest_path = template_folder / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_manifest(template_folder: Path, manifest: dict) -> None:
    """Write manifest.json back to a template folder."""
    manifest_path = template_folder / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def validate_manifest_completeness(manifest: dict) -> list[str]:
    """
    Check that a manifest has all required fields per MINIMUM_MANIFEST_SCHEMA.md.
    Returns a list of missing/invalid field paths.
    """
    issues = []

    # Required identity fields
    for field in ("template_id", "template_family", "template_version", "display_name", "status"):
        if field not in manifest or not manifest[field]:
            issues.append(f"manifest.{field} is missing or empty")

    # fingerprints.page_signature.page_count
    fps = manifest.get("fingerprints", {})
    if "page_signature" not in fps or "page_count" not in fps.get("page_signature", {}):
        issues.append("manifest.fingerprints.page_signature.page_count is missing")

    # schema_ref
    sr = manifest.get("schema_ref", {})
    for field in ("schema_path", "blank_pdf_path"):
        if not sr.get(field):
            issues.append(f"manifest.schema_ref.{field} is missing or empty")

    # runtime_hints required fields
    rh = manifest.get("runtime_hints", {})
    for field in ("default_input_mode", "primary_language", "alignment_mode"):
        if not rh.get(field):
            issues.append(f"manifest.runtime_hints.{field} is missing or empty")

    return issues


def validate_schema_completeness(schema: dict) -> list[str]:
    """
    Check that a schema has all required fields per MINIMUM_SCHEMA_FIELD_FORMAT.md.
    Returns a list of missing/invalid issues.
    """
    issues = []

    if "template_id" not in schema:
        issues.append("schema.template_id is missing")

    if "fields" not in schema or not isinstance(schema["fields"], list):
        issues.append("schema.fields is missing or not a list")

    # Validate each field
    for i, field in enumerate(schema.get("fields", [])):
        for req in ("field_id", "field_name", "field_label", "page_number", "bbox", "field_type", "input_mode"):
            if req not in field:
                issues.append(f"schema.fields[{i}].{req} is missing")

        rh = field.get("runtime_hints", {})
        if not rh.get("preferred_extractor"):
            issues.append(f"schema.fields[{i}].runtime_hints.preferred_extractor is missing")

    return issues


def activate_template(template_id: str, templates_dir: Optional[Path] = None) -> bool:
    """
    Promote a draft template to active status.

    Parameters
    ----------
    template_id : str
        The template ID to activate.
    templates_dir : Path, optional
        Override the templates directory.

    Returns
    -------
    bool
        True if activation succeeded, False otherwise.
    """
    if templates_dir is None:
        templates_dir = TEMPLATES_DIR
    else:
        templates_dir = Path(templates_dir)  # ensure Path type for path operations
    template_folder = templates_dir / template_id
    manifest_path = template_folder / "manifest.json"

    if not manifest_path.exists():
        logger.error(f"Cannot activate {template_id}: manifest not found")
        return False

    manifest = _load_manifest(template_folder)
    if not manifest:
        logger.error(f"Cannot activate {template_id}: failed to load manifest")
        return False

    # Validate completeness before activation
    issues = validate_manifest_completeness(manifest)
    if issues:
        logger.warning(f"Template {template_id} has completeness issues: {issues}")

    # Validate schema exists
    schema_path_value = manifest.get("schema_ref", {}).get("schema_path", "schema.json")
    schema_path = template_folder / schema_path_value.split("/")[-1]
    if not schema_path.exists():
        logger.error(f"Cannot activate {template_id}: schema not found at {schema_path}")
        return False

    # Validate schema completeness
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        schema_issues = validate_schema_completeness(schema)
        if schema_issues:
            logger.warning(f"Template {template_id} schema has issues: {schema_issues}")
    except Exception as e:
        logger.error(f"Cannot activate {template_id}: failed to load schema: {e}")
        return False

    # Promote to active
    manifest["status"] = "active"
    _write_manifest(template_folder, manifest)

    # Reload registry so the newly activated template is picked up
    registry = TemplateRegistry(templates_dir=templates_dir)
    registry.reload()

    logger.info(f"Template {template_id} promoted to active")
    return True


def keep_draft(template_id: str, templates_dir: Optional[Path] = None) -> bool:
    """
    Explicitly keep a template in draft status. Useful when auto-generation
    produced a template that needs review before use.
    """
    if templates_dir is None:
        templates_dir = TEMPLATES_DIR
    else:
        templates_dir = Path(templates_dir)
    template_folder = templates_dir / template_id
    manifest_path = template_folder / "manifest.json"

    if not manifest_path.exists():
        return False

    manifest = _load_manifest(template_folder)
    if not manifest:
        return False

    manifest["status"] = "draft"
    _write_manifest(template_folder, manifest)

    # Reload registry so the draft template is NOT picked up (only active templates load)
    registry = TemplateRegistry(templates_dir=templates_dir)
    registry.reload()

    logger.info(f"Template {template_id} kept as draft")
    return True


def reload_registry(templates_dir: Optional[Path] = None) -> TemplateRegistry:
    """
    Reload the template registry, returning the refreshed instance.
    Call this after registration or activation changes.
    """
    if templates_dir is None:
        templates_dir = TEMPLATES_DIR
    else:
        templates_dir = Path(templates_dir)
    registry = TemplateRegistry(templates_dir=templates_dir)
    registry.reload()
    return registry
