"""
Module T1: Document Role Classifier
Classifies an incoming PDF into one of three roles after basic validation/inspection:

- blank_template_candidate  — appears to be a clean blank/canonical form
- filled_instance           — appears to be a filled-in document
- invalid_or_unsupported     — cannot be classified as either

This is the first branching point for the three-lane runtime architecture.
Conservative by design: prefer false negatives (missing a blank candidate) over
false positives (registering a filled document as a template).

Signals used (from PDFInspectionResult):
- acroform_field_names  — structured form fields suggest a template-like document
- is_born_digital       — native PDF structure (AcroForm / text) vs scanned image-only
- is_scanned            — image-only PDF (no native structure)
- is_hybrid             — both native text and images
- page_count            — multi-page documents are more likely structured templates

Additionally, when pdf_path is provided, field values are read via pypdf to
determine if AcroForm fields contain actual data (filled form) or are empty
(blank template candidate).

Policy: prefer false negatives over false positives.
It is safer to miss a blank template candidate than to auto-register a filled document.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pypdf

from common.pdf_inspector import PDFInspectionResult


# ─── Threshold constants ────────────────────────────────────────────────────────

# Minimum AcroForm fields required to consider a document template-like
_MIN_ACROFORM_FIELDS_FOR_BLANK = 3

# If filled fields are estimated above this fraction of total fields, classify as filled
_FILLED_FIELD_RATIO_THRESHOLD = 0.05  # >5% of fields filled → likely a filled instance


# ─── Document role enum ────────────────────────────────────────────────────────

class DocumentRole:
    BLANK_TEMPLATE_CANDIDATE = "blank_template_candidate"
    FILLED_INSTANCE = "filled_instance"
    INVALID_OR_UNSUPPORTED = "invalid_or_unsupported"


# ─── Result type ───────────────────────────────────────────────────────────────

@dataclass
class DocumentRoleResult:
    role: str
    confidence: float          # 0.0–1.0, how confident the classification is
    reasons: list[str]         # human-readable signals that drove the decision
    blank_signals: dict        # raw signal values for observability
    filled_signals: dict       # raw signal values for observability


# ─── Field-value helpers ──────────────────────────────────────────────────────

def _count_filled_fields(pdf_path: Optional[str], acroform_count: int) -> tuple[int, float]:
    """
    Read AcroForm field values via pypdf and count how many contain non-empty data.

    Returns (filled_count, filled_ratio) where ratio = filled_count / total_fields.
    Returns (0, 0.0) if pdf_path is None, file cannot be read, or no fields exist.
    """
    if pdf_path is None or acroform_count == 0:
        return 0, 0.0

    try:
        reader = pypdf.PdfReader(pdf_path)
        fields = reader.get_fields()
        if fields is None:
            return 0, 0.0

        filled = 0
        for field in fields.values():
            raw_val = field.get("/V", "")
            val_str = str(raw_val).strip()
            # Treat empty string, None-equivalent, and "Off" (checkbox) as unfilled
            if val_str and val_str not in ("", "Off", "false", "None"):
                filled += 1

        ratio = filled / acroform_count if acroform_count > 0 else 0.0
        return filled, ratio
    except Exception:
        # If we can't read fields, be conservative — assume nothing filled
        return 0, 0.0


# ─── Heuristics ────────────────────────────────────────────────────────────────

def _score_blank_candidate(
    insp: PDFInspectionResult,
    pdf_path: Optional[str] = None,
) -> tuple[float, dict, list[str]]:
    """
    Compute a 0.0–1.0 score for blank_template_candidate.
    Returns (score, signals_dict, reasons_list).

    If pdf_path is provided and the PDF has AcroForm fields, field values are
    read to check whether any fields contain non-empty data. A blank template
    candidate should have all (or nearly all) fields empty.
    """
    signals: dict = {}
    reasons: list[str] = []

    # Signal 1: Strong AcroForm presence — strongest indicator of template structure
    acroform_count = len(insp.acroform_field_names)
    signals["acroform_field_count"] = acroform_count
    if acroform_count >= _MIN_ACROFORM_FIELDS_FOR_BLANK:
        reasons.append(f"Strong AcroForm structure ({acroform_count} fields)")
    elif acroform_count > 0:
        reasons.append(f"AcroForm present but sparse ({acroform_count} fields)")

    # Signal 2: Born-digital structure
    signals["is_born_digital"] = insp.is_born_digital
    if insp.is_born_digital:
        reasons.append("Born-digital (native PDF structure)")

    # Signal 3: Not scanned-only
    signals["is_scanned"] = insp.is_scanned
    if not insp.is_scanned:
        reasons.append("Not image-only scanned")

    # Signal 4: Not hybrid (hybrid = native text + images = likely filled mixed doc)
    signals["is_hybrid"] = insp.is_hybrid
    if not insp.is_hybrid:
        reasons.append("Not hybrid (no mixed text+image content)")

    # Signal 5: Reasonable page count for a form template
    signals["page_count"] = insp.page_count
    if 1 <= insp.page_count <= 5:
        reasons.append(f"Template-like page count ({insp.page_count} pages)")

    # Signal 6: Stable AcroForm leaf names (template forms have structured field names)
    # Heuristic: if leaf names contain underscores/caps (form-like naming) vs random strings
    structured_name_count = _count_structured_field_names(insp.acroform_field_names)
    signals["structured_field_names"] = structured_name_count
    if structured_name_count > 0:
        reasons.append(f"Structured form field names ({structured_name_count} of {acroform_count})")

    # Signal 7 (key): Check actual field values via pypdf
    # A blank template should have all/nearly-all fields empty
    filled_field_count, filled_ratio = _count_filled_fields(pdf_path, acroform_count)
    signals["filled_field_count"] = filled_field_count
    signals["filled_field_ratio"] = filled_ratio
    if filled_field_count > 0:
        reasons.append(f"Fields with data: {filled_field_count}/{acroform_count}")

    # Score computation
    score = 0.0
    if acroform_count >= _MIN_ACROFORM_FIELDS_FOR_BLANK:
        score += 0.40
    elif acroform_count > 0:
        score += 0.15

    if insp.is_born_digital:
        score += 0.20

    if not insp.is_scanned:
        score += 0.15

    if not insp.is_hybrid:
        score += 0.10

    if 1 <= insp.page_count <= 5:
        score += 0.10

    if structured_name_count >= _MIN_ACROFORM_FIELDS_FOR_BLANK:
        score += 0.05

    # Penalize blank score if fields are filled
    # Even 1-2 filled fields in a 181-field form means it's a filled instance
    if filled_field_count > 0:
        # Strong penalty: even a few filled fields disqualify blank candidacy
        score *= (1.0 - min(filled_ratio * 2.0, 0.80))
        if filled_ratio >= _FILLED_FIELD_RATIO_THRESHOLD:
            score = 0.0  # too many filled fields → cannot be blank

    return max(score, 0.0), signals, reasons


def _score_filled_instance(
    insp: PDFInspectionResult,
    pdf_path: Optional[str] = None,
) -> tuple[float, dict, list[str]]:
    """
    Compute a 0.0–1.0 score for filled_instance.
    Returns (score, signals_dict, reasons_list).
    """
    signals: dict = {}
    reasons: list[str] = []

    # Signal 1: Scanned-only document — filled forms may be scanned
    signals["is_scanned"] = insp.is_scanned
    if insp.is_scanned:
        reasons.append("Image-only (scanned)")

    # Signal 2: Hybrid document — likely a filled form with annotations/images
    signals["is_hybrid"] = insp.is_hybrid
    if insp.is_hybrid:
        reasons.append("Hybrid (native text + images)")

    # Signal 3: Born-digital but potentially filled
    signals["is_born_digital"] = insp.is_born_digital
    if insp.is_born_digital:
        reasons.append("Born-digital (could be filled)")

    # Signal 4: Sparse or absent AcroForm — filled documents may not have form fields
    acroform_count = len(insp.acroform_field_names)
    signals["acroform_field_count"] = acroform_count
    if acroform_count == 0:
        reasons.append("No AcroForm fields")

    # Signal 5: Multi-page filled documents
    if insp.page_count > 5:
        reasons.append(f"Lots of pages ({insp.page_count}) — less typical for simple template")

    # Signal 6: Field values via pypdf — if we can read values, use them
    filled_field_count, filled_ratio = _count_filled_fields(pdf_path, acroform_count)
    signals["filled_field_count"] = filled_field_count
    signals["filled_field_ratio"] = filled_ratio
    if filled_field_count > 0:
        reasons.append(f"Fields with data: {filled_field_count}/{acroform_count}")

    # Score computation
    score = 0.0

    if insp.is_scanned:
        score += 0.35

    if insp.is_hybrid:
        score += 0.25

    if acroform_count == 0 and (insp.is_born_digital or insp.is_hybrid):
        # Born-digital/hybrid but no AcroForm — could be a filled non-form PDF
        score += 0.20

    if acroform_count > 0 and acroform_count < _MIN_ACROFORM_FIELDS_FOR_BLANK:
        score += 0.10

    if insp.page_count > 10:
        score += 0.10

    # Boost filled score when field values are detected
    if filled_field_count > 0:
        score += min(filled_ratio * 1.5, 0.40)  # up to +0.40 for heavily filled forms

    return min(score, 1.0), signals, reasons


def _count_structured_field_names(field_names: list[str]) -> int:
    """
    Heuristic: count field names that look like structured form field names.
    Template forms typically have names with underscores, mixed case, or path-like structure.
    e.g. 'form1[0].Page1[0].PartA[0].Last_Name_Fill[0]' -> structured
    e.g. 'img_001' or random hex -> not structured
    """
    if not field_names:
        return 0
    structured = 0
    for name in field_names:
        # Structured indicators: contains path separators, underscores, mixed case
        has_path = "[" in name or "." in name
        has_underscore = "_" in name
        # Check for mixed case (at least one upper and one lower)
        has_mixed_case = any(c.isupper() for c in name) and any(c.islower() for c in name)
        if has_path or (has_underscore and has_mixed_case):
            structured += 1
    return structured


# ─── Main classifier ───────────────────────────────────────────────────────────

def classify_document_role(
    insp: PDFInspectionResult,
    pdf_path: Optional[str] = None,
) -> DocumentRoleResult:
    """
    Classify a PDF inspection result into a document role.

    Classification logic:
    1. If the document has NO strong template signals AND no strong filled signals,
       return invalid_or_unsupported.
    2. If blank_score > filled_score by a meaningful margin, return blank_template_candidate.
    3. Otherwise return filled_instance.

    Conservative bias: require blank_score to exceed filled_score by at least 0.15
    to classify as blank_template_candidate. This prevents registering borderline docs.

    Parameters
    ----------
    insp : PDFInspectionResult
        The pre-computed PDF inspection result.
    pdf_path : str, optional
        Path to the PDF file. If provided and the PDF has AcroForm fields, field
        values are read via pypdf to determine whether fields are filled or empty.
    """
    blank_score, blank_signals, blank_reasons = _score_blank_candidate(insp, pdf_path)
    filled_score, filled_signals, filled_reasons = _score_filled_instance(insp, pdf_path)

    # Default: invalid_or_unsupported if both scores are very low
    if blank_score < 0.20 and filled_score < 0.20:
        return DocumentRoleResult(
            role=DocumentRole.INVALID_OR_UNSUPPORTED,
            confidence=0.5,
            reasons=[
                f"Neither blank nor filled signals strong (blank={blank_score:.2f}, filled={filled_score:.2f})"
            ],
            blank_signals=blank_signals,
            filled_signals=filled_signals,
        )

    # Conservative: blank requires a meaningful margin over filled
    # This prevents borderline documents from being auto-registered
    BLANK_MARGIN = 0.15

    if blank_score > filled_score + BLANK_MARGIN:
        return DocumentRoleResult(
            role=DocumentRole.BLANK_TEMPLATE_CANDIDATE,
            confidence=round(blank_score, 3),
            reasons=blank_reasons,
            blank_signals=blank_signals,
            filled_signals=filled_signals,
        )

    # Default: treat as filled
    return DocumentRoleResult(
        role=DocumentRole.FILLED_INSTANCE,
        confidence=round(filled_score, 3),
        reasons=filled_reasons if filled_reasons else ["Default classification — fell through to filled_instance"],
        blank_signals=blank_signals,
        filled_signals=filled_signals,
    )
