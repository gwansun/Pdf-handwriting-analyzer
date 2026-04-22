"""
Module T5: Registration Orchestration
Main entrypoint for blank-PDF template auto-registration.

Responsibilities:
1. Accept a blank PDF path and inspection result
2. Generate a template identity
3. Create the template folder
4. Copy/store the blank PDF into the template folder
5. Generate manifest.json via manifest_builder
6. Generate schema.json via schema_builder
7. Activate as draft (or active after review in post-MVP)
8. Reload the registry so the new template is immediately available

Does NOT handle:
- Matched-template extraction
- Unknown filled-PDF fallback extraction
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from common.config import TEMPLATES_DIR, ErrorCode
from common.pdf_inspector import PDFInspectionResult
from template.activation import keep_draft, reload_registry
from template.manifest_builder import build_manifest, generate_template_identity
from template.registration_types import (
    ArtifactWriteResult,
    GeneratedTemplateArtifacts,
    RegistrationResult,
    TemplateIdentity,
)
from template.schema_builder import build_schema

logger = logging.getLogger("registration")


# ─── Artifact writing helpers ───────────────────────────────────────────────────

def _write_artifact(path: Path, data: dict) -> ArtifactWriteResult:
    """Write a JSON artifact to disk, returning success/error."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return ArtifactWriteResult(path=str(path), success=True)
    except Exception as e:
        return ArtifactWriteResult(path=str(path), success=False, error=str(e))


def _copy_blank_pdf(src_path: str, dest_path: Path) -> ArtifactWriteResult:
    """Copy the blank PDF into the template folder."""
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)
        return ArtifactWriteResult(path=str(dest_path), success=True)
    except Exception as e:
        return ArtifactWriteResult(path=str(dest_path), success=False, error=str(e))


# ─── Collision / safety helpers ──────────────────────────────────────────────────

def _check_existing_template(template_id: str, templates_dir: Path) -> bool:
    """Return True if a template with this ID already exists."""
    folder = templates_dir / template_id
    return folder.exists() and (folder / "manifest.json").exists()


def _generate_unique_template_id(base_id: str, templates_dir: Path) -> str:
    """Generate a unique template_id by appending a suffix if collision exists."""
    template_id = base_id
    counter = 1
    while _check_existing_template(template_id, templates_dir):
        template_id = f"{base_id}_{counter}"
        counter += 1
    return template_id


# ─── Main registration function ─────────────────────────────────────────────────

def register_blank_pdf(
    pdf_path: str,
    inspection: PDFInspectionResult,
    template_family_hint: Optional[str] = None,
    templates_dir: Optional[Path] = None,
    activate: bool = False,
) -> RegistrationResult:
    """
    Register a blank PDF as a new template.

    Parameters
    ----------
    pdf_path : str
        Absolute path to the blank PDF file.
    inspection : PDFInspectionResult
        The result of inspecting the blank PDF.
    template_family_hint : str, optional
        Override the template family name. Otherwise derived from PDF metadata.
    templates_dir : Path, optional
        Override the templates root directory. Defaults to TEMPLATES_DIR.
    activate : bool
        If True, promote to active immediately. If False (default), keep as draft.

    Returns
    -------
    RegistrationResult
        A structured result with success status, generated artifacts, and any errors.
    """
    if templates_dir is None:
        templates_dir = TEMPLATES_DIR
    else:
        templates_dir = Path(templates_dir)  # ensure Path type for path operations
    warnings: list[str] = []
    errors: list[str] = []
    artifacts = GeneratedTemplateArtifacts()

    # ── 1. Generate template identity ───────────────────────────────────────────
    identity = generate_template_identity(inspection, template_family_hint=template_family_hint)

    # Make template_id unique if collision exists
    identity.template_id = _generate_unique_template_id(identity.template_id, templates_dir)

    if _check_existing_template(identity.template_id, templates_dir):
        errors.append(
            f"Template ID collision after suffix retry: {identity.template_id}. "
            "Registration aborted."
        )
        return RegistrationResult(
            success=False,
            template_id=identity.template_id,
            errors=errors,
            activation_status="error",
        )

    template_folder = templates_dir / identity.template_id

    # ── 2. Create template folder ───────────────────────────────────────────────
    try:
        template_folder.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Failed to create template folder: {e}")
        return RegistrationResult(
            success=False,
            template_id=identity.template_id,
            errors=errors,
            activation_status="error",
        )

    # ── 3. Copy blank PDF into template folder ─────────────────────────────────
    blank_pdf_filename = f"{identity.template_id}.pdf"
    blank_pdf_dest = template_folder / blank_pdf_filename
    pdf_copy_result = _copy_blank_pdf(pdf_path, blank_pdf_dest)
    if pdf_copy_result.success:
        artifacts.blank_pdf_path = pdf_copy_result.path
    else:
        warnings.append(f"Failed to copy blank PDF: {pdf_copy_result.error}")

    # ── 4. Generate manifest.json ───────────────────────────────────────────────
    manifest = build_manifest(
        template_folder=str(template_folder),
        blank_pdf_filename=blank_pdf_filename,
        identity=identity,
        inspection=inspection,
        status="draft",
    )

    manifest_path = template_folder / "manifest.json"
    manifest_result = _write_artifact(manifest_path, manifest)
    if manifest_result.success:
        artifacts.manifest_path = manifest_result.path
    else:
        errors.append(f"Failed to write manifest.json: {manifest_result.error}")

    # ── 5. Generate schema.json ────────────────────────────────────────────────
    schema = build_schema(
        template_id=identity.template_id,
        inspection=inspection,
        pdf_path=pdf_path,
    )

    schema_path = template_folder / "schema.json"
    schema_result = _write_artifact(schema_path, schema)
    if schema_result.success:
        artifacts.schema_path = schema_result.path
    else:
        errors.append(f"Failed to write schema.json: {schema_result.error}")

    # ── 6. Determine activation status ─────────────────────────────────────────
    # Auto-generated templates always start as draft for safety
    activation_status = "draft"

    if activate:
        # Write schema before activation check (activation validates schema exists)
        if not errors:
            activated = keep_draft(identity.template_id, templates_dir=templates_dir)
            if activated:
                activation_status = "active"
        else:
            warnings.append("Skipped activation due to errors during artifact generation")
            activation_status = "draft"
    else:
        # Keep as draft (default)
        keep_draft(identity.template_id, templates_dir=templates_dir)

    # ── 7. Reload registry so the new template is immediately visible ────────────
    try:
        reload_registry(templates_dir=templates_dir)
    except Exception as e:
        warnings.append(f"Registry reload failed (template may still be created): {e}")

    # ── 8. Final result ───────────────────────────────────────────────────────
    success = len(errors) == 0 and artifacts.manifest_path is not None and artifacts.schema_path is not None

    logger.info(
        f"Template registration {'succeeded' if success else 'failed'} "
        f"for {identity.template_id}: errors={len(errors)}, warnings={len(warnings)}"
    )

    return RegistrationResult(
        success=success,
        template_id=identity.template_id,
        template_folder=str(template_folder),
        artifacts=artifacts,
        activation_status=activation_status,
        warnings=warnings,
        errors=errors,
        identity=identity,
    )
