"""
Module T3: Manifest Builder
Generates a template manifest.json from a blank PDF inspection result.

Inputs:
- PDFInspectionResult from pdf_inspector
- TemplateIdentity (template_id, family, version, display_name)
- Template folder path
- Source blank PDF path

Outputs:
- A dict matching the MINIMUM_MANIFEST_SCHEMA.md structure
- Does NOT write to disk — caller is responsible for writing
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional

from common.pdf_inspector import PDFInspectionResult
from template.registration_types import GeneratedTemplateArtifacts, TemplateIdentity


def _generate_template_id_from_inspection(insp: PDFInspectionResult) -> str:
    """
    Generate a stable template_id from the PDF's inspection fingerprint.
    Uses a short hash of the AcroForm field names + page_count + page_sizes
    to create a stable but unique identifier.
    """
    # Build a fingerprint string from structural signals
    acroform_count = len(insp.acroform_field_names)
    page_sig = f"{insp.page_count}_{insp.page_sizes}"

    # Use field names if available (they're the strongest structural signal)
    if insp.acroform_field_names:
        field_sig = "_".join(sorted(insp.acroform_field_names[:10]))  # first 10 as sig
    else:
        field_sig = "no_acroform"

    raw = f"{acroform_count}_{page_sig}_{field_sig}"
    hash_suffix = hashlib.md5(raw.encode()).hexdigest()[:6]

    return f"auto_{hash_suffix}"


def _build_fingerprints(insp: PDFInspectionResult) -> dict:
    """Build the fingerprints section of the manifest."""
    return {
        "metadata": dict(insp.metadata),
        "acroform": {
            "field_count": len(insp.acroform_field_names),
            "field_names": insp.acroform_field_names,
        },
        "page_signature": {
            "page_count": insp.page_count,
            "page_sizes": [
                {"width": w, "height": h} for w, h in insp.page_sizes
            ] if insp.page_sizes else [],
        },
        "anchor_text": {
            "phrases": [],  # populated by anchor_builder if used
        },
        "visual_anchor": {},  # placeholder for future thumbnail hashing
    }


def _build_runtime_hints() -> dict:
    """Build the runtime_hints section with safe MVP defaults."""
    return {
        "default_input_mode": "mixed",
        "primary_language": "en",
        "alignment_mode": "strict",
        "unknown_field_policy": "review",
        "preferred_extractors": [],
    }


def build_manifest(
    template_folder: str,
    blank_pdf_filename: str,
    identity: TemplateIdentity,
    inspection: PDFInspectionResult,
    status: str = "draft",
) -> dict:
    """
    Build a complete manifest.json dict from a blank PDF inspection result.

    Parameters
    ----------
    template_folder : str
        Absolute path to the template folder (e.g. /.../templates/abc123/).
    blank_pdf_filename : str
        Filename of the blank PDF within the template folder.
    identity : TemplateIdentity
        Template identity fields (template_id, family, version, display_name).
    inspection : PDFInspectionResult
        Inspection result from pdf_inspector.
    status : str
        Initial status. Defaults to "draft" as recommended.

    Returns
    -------
    dict
        A dict suitable for serializing to manifest.json.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest = {
        "template_id": identity.template_id,
        "template_family": identity.template_family,
        "template_version": identity.template_version,
        "display_name": identity.display_name or identity.template_id,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "fingerprints": _build_fingerprints(inspection),
        "schema_ref": {
            "schema_path": f"templates/{identity.template_id}/schema.json",
            "blank_pdf_path": f"templates/{identity.template_id}/{blank_pdf_filename}",
        },
        "runtime_hints": _build_runtime_hints(),
    }

    return manifest


def generate_template_identity(
    inspection: PDFInspectionResult,
    template_family_hint: Optional[str] = None,
) -> TemplateIdentity:
    """
    Generate a TemplateIdentity from a blank PDF inspection result.

    Parameters
    ----------
    inspection : PDFInspectionResult
        The PDF inspection result.
    template_family_hint : str, optional
        If provided, use this as the template_family. Otherwise derive from metadata.

    Returns
    -------
    TemplateIdentity
    """
    template_id = _generate_template_id_from_inspection(inspection)

    # Derive template_family from metadata if no hint provided
    if template_family_hint:
        template_family = template_family_hint
    else:
        # Try to extract from PDF metadata (e.g., form name in title)
        title = inspection.metadata.get("/Title", "") or ""
        if title:
            # Use first word of title as family
            template_family = title.strip().split()[0].lower() if title else "unknown"
        else:
            template_family = "auto"

    return TemplateIdentity(
        template_id=template_id,
        template_family=template_family,
        template_version="1.0",
        display_name=f"Auto-registered template {template_id}",
    )
