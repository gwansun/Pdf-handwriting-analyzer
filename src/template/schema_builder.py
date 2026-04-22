"""
Module T4: Schema Builder
Generates an initial schema.json from a blank PDF's AcroForm fields.

Inputs:
- PDFInspectionResult (contains acroform_field_names, page_sizes)
- Template ID
- Source blank PDF path (for extracting AcroForm widget rectangles)

Outputs:
- A dict matching the MINIMUM_SCHEMA_FIELD_FORMAT.md structure
- Does NOT write to disk — caller is responsible for writing

Heuristics for field type inference:
- Field name contains "date" / "Date" -> field_type="date"
- Field name contains "name" / "Name" / "last" / "first" -> field_type="text", input_mode="handwritten"
- Field name contains "sig" / "signature" -> field_type="signature"
- Field name contains "check" / "box" -> field_type="checkbox"
- Field name contains "phone" / "tel" -> field_type="text", input_mode="handwritten"
- Field name contains "sin" / "ssn" / "social" -> field_type="text", input_mode="mixed"
- Default -> field_type="text", input_mode="mixed"

Heuristics for field_label inference:
- Derive from leaf name by replacing underscores with spaces and title-casing
- e.g. "Last_Name_Fill" -> "Last Name Fill"
"""

import re
from typing import Optional

from common.pdf_inspector import PDFInspectionResult
from template.registration_types import TemplateIdentity


# ─── Field type inference ────────────────────────────────────────────────────────

_QUALITATIVE_TYPES = {
    "date": "date",
    "year": "number",
    "phone": "text",
    "tel": "text",
    "sin": "text",
    "ssn": "text",
    "social": "text",
    "email": "text",
    "address": "text",
    "currency": "number",
    "money": "number",
    "checkbox": "checkbox",
    "check": "checkbox",
    "box": "checkbox",
    "signature": "signature",
    "sig": "signature",
    "radio": "radio",
    "name": "text",
    "last": "text",
    "first": "text",
}


def _infer_field_type(field_name: str) -> tuple[str, str]:
    """
    Infer field_type and input_mode from a field name.
    Returns (field_type, input_mode).
    """
    name_lower = field_name.lower()

    # Check for checkbox/radio
    if any(k in name_lower for k in ("checkbox", "check", "box")):
        return "checkbox", "selection"
    if "radio" in name_lower:
        return "radio", "selection"

    # Check for signature
    if any(k in name_lower for k in ("signature", "sig")):
        return "signature", "signature"

    # Check for date
    if "date" in name_lower or "dob" in name_lower:
        return "date", "typed"

    # Check for number/currency fields
    if any(k in name_lower for k in ("year", "currency", "money", "amount", "total")):
        return "number", "typed"

    # Check for typed-only fields (form labels, printed text)
    typed_indicators = ("title", "header", "instruction", "note")
    if any(k in name_lower for k in typed_indicators):
        return "text", "typed"

    # Check for handwritten fields
    handwritten_indicators = ("name", "last", "first", "address", "phone", "sin", "ssn", "email")
    if any(k in name_lower for k in handwritten_indicators):
        return "text", "handwritten"

    # Default: mixed
    return "text", "mixed"


def _leaf_name(qualified_name: str) -> str:
    """Extract leaf field name from a fully-qualified AcroForm field path."""
    last = qualified_name.split(".")[-1]
    return last.rstrip("]").split("[")[0]


def _derive_field_label(leaf_name: str) -> str:
    """
    Derive a human-readable field_label from the AcroForm leaf name.
    e.g. 'Last_Name_Fill' -> 'Last Name Fill'
          'form1[0].Page1[0].PartA[0].Last_Name_Fill[0]' -> 'Last Name Fill'
    """
    label = leaf_name
    # Remove common suffixes
    for suffix in ("_Fill", "_fill", "_Input", "_input", "_Field", "_field"):
        if label.endswith(suffix):
            label = label[:-len(suffix)]
    # Replace underscores and camelCase with spaces
    label = re.sub(r"([a-z])([A-Z])", r"\1 \2", label)  # camelCase -> words
    label = label.replace("_", " ").replace(".", " ").replace("[", " ").replace("]", " ")
    # Title case and clean up
    label = " ".join(word.capitalize() for word in label.split() if word)
    return label or leaf_name


def _generate_field_id(leaf_name: str, index: int) -> str:
    """Generate a stable field_id from the leaf name."""
    # Clean: lowercase, underscores, alphanumeric only
    clean = re.sub(r"[^a-z0-9_]", "", leaf_name.lower())
    if not clean:
        clean = f"field_{index}"
    return f"{clean}_{index}"


def _load_acroform_widget_rectangles(
    pdf_path: str,
    field_names: list[str],
) -> dict[str, list[float]]:
    """
    Load widget rectangle bboxes for AcroForm fields from a PDF.

    Returns a dict mapping leaf field name -> [x0, y0, x1, y1] in PDF points.
    Returns {} if extraction fails.
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path, strict=False)
        if reader.is_encrypted:
            reader.decrypt("")
        fields = reader.get_fields() or {}
        result = {}
        for fname, fobj in fields.items():
            leaf = _leaf_name(fname)
            if leaf in field_names:
                # Try to get the widget rectangle from /Rect
                if "/Rect" in fobj:
                    rect = fobj["/Rect"]
                    if isinstance(rect, pypdf.objects.ArrayObject):
                        vals = [float(v) for v in rect]
                        if len(vals) == 4:
                            result[leaf] = vals
                # Also check in field kids
                if "/Kids" in fobj:
                    for kid in fobj["/Kids"]:
                        if hasattr(kid, "get") and "/Rect" in kid:
                            rect = kid["/Rect"]
                            if isinstance(rect, pypdf.objects.ArrayObject):
                                vals = [float(v) for v in rect]
                                if len(vals) == 4:
                                    result[leaf] = vals
                                    break
        return result
    except Exception:
        return {}


def build_schema(
    template_id: str,
    inspection: PDFInspectionResult,
    pdf_path: str,
) -> dict:
    """
    Build a complete schema.json dict from a blank PDF inspection.

    Parameters
    ----------
    template_id : str
        The assigned template ID.
    inspection : PDFInspectionResult
        The PDF inspection result.
    pdf_path : str
        Path to the source blank PDF (for extracting widget rectangles).

    Returns
    -------
    dict
        A dict suitable for serializing to schema.json.
    """
    # Load widget rectangles
    acroform_rects = {}
    if inspection.acroform_field_names and inspection.is_born_digital:
        acroform_rects = _load_acroform_widget_rectangles(
            pdf_path, inspection.acroform_field_names
        )

    # Build page list
    pages = []
    for i, (w, h) in enumerate(inspection.page_sizes, start=1):
        pages.append({
            "page_number": i,
            "width": float(w),
            "height": float(h),
            "unit": "pt",
        })

    # Build field list
    fields = []
    for i, fq_name in enumerate(inspection.acroform_field_names):
        leaf = _leaf_name(fq_name)
        bbox = acroform_rects.get(leaf, [0, 0, 0, 0])
        field_type, input_mode = _infer_field_type(leaf)
        field_label = _derive_field_label(leaf)
        field_id = _generate_field_id(leaf, i)

        # Estimate page number from field position if we have many fields
        # For AcroForm-only, we can't reliably map fields to pages without widget /Page refs
        # Default to page 1 for now
        page_number = 1

        field_def = {
            "field_id": field_id,
            "field_name": leaf,
            "field_label": field_label,
            "page_number": page_number,
            "bbox": bbox,
            "field_type": field_type,
            "input_mode": input_mode,
            "required": False,
            "runtime_hints": {
                "preferred_extractor": "native_text_first" if input_mode == "typed" else "handwriting_ocr",
                "language_hint": "en",
            },
            "validation_rules": [],
        }
        fields.append(field_def)

    schema = {
        "template_id": template_id,
        "pages": pages,
        "fields": fields,
    }

    return schema
