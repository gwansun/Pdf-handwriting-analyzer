"""
Module C: Template Matcher
Compares an incoming PDF's inspection results against registered template fingerprints.
Uses a weighted multi-signal scoring approach. Returns matched/unknown status.
"""

from dataclasses import dataclass
from typing import Optional

from .config import TEMPLATE_MATCH_THRESHOLD, ErrorCode
from .pdf_inspector import PDFInspectionResult
from .template_registry import TemplateRecord, TemplateRegistry
from .response_builder import ErrorDetail


class TemplateMatchingError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


@dataclass
class MatchResult:
    template_id: Optional[str]
    template_match_status: str  # matched | unknown
    match_score: float


@dataclass
class MatchSignals:
    metadata_score: float = 0.0
    acroform_score: float = 0.0
    page_structure_score: float = 0.0
    anchor_text_score: float = 0.0
    visual_anchor_score: float = 0.0
    final_score: float = 0.0


# Weights from TEMPLATE_MATCHING_STRATEGY.md
_WEIGHTS = {
    "metadata": 0.20,
    "acroform": 0.30,
    "page_structure": 0.20,
    "anchor_text": 0.20,
    "visual_anchor": 0.10,
}


def compute_metadata_score(inspection: PDFInspectionResult, template: TemplateRecord) -> float:
    """
    Compare PDF metadata against template metadata fingerprint.
    Returns 0.0–1.0 similarity score.
    Keys are normalized by stripping leading '/' to match manifest format.
    """
    tmpl_meta = template.fingerprints.metadata
    if not tmpl_meta:
        return 0.5  # neutral if template has no metadata fingerprint

    # Normalize inspection metadata keys (pypdf uses '/KeyName' format)
    insp_meta = {k.lstrip("/").lower(): v for k, v in inspection.metadata.items()}

    matches = 0
    total = len(tmpl_meta)

    for key, tmpl_value in tmpl_meta.items():
        key_lower = key.lower()
        insp_value = insp_meta.get(key_lower, "")
        if isinstance(tmpl_value, str) and isinstance(insp_value, str):
            if tmpl_value.strip().lower() == insp_value.strip().lower():
                matches += 1
        elif key_lower in insp_meta and insp_meta[key_lower] == tmpl_value:
            matches += 1

    return matches / total if total > 0 else 0.5


def _leaf_name(qualified_name: str) -> str:
    """
    Extract the leaf field name from a fully-qualified AcroForm field path.
    e.g. 'form1[0].Page1[0].PartA[0].Ident[0].Last_Name_Fill[0]' -> 'Last_Name_Fill'
    """
    last = qualified_name.split(".")[-1]
    return last.rstrip("]").split("[")[0]


def compute_acroform_score(inspection: PDFInspectionResult, template: TemplateRecord) -> float:
    """
    Compare AcroForm field structure against template fingerprint.
    This is the strongest signal for fillable forms like T2200.
    Uses leaf-name comparison to handle hierarchical PDF field paths.

    Scoring: precision-oriented — what fraction of the template's leaf field names
    are present in the incoming PDF's AcroForm field names. This is the right metric
    because the template defines what fields SHOULD exist; the PDF may have fewer or
    the same fields (filled-in forms don't add new field slots).
    """
    tmpl_acroform = template.fingerprints.acroform
    if not tmpl_acroform:
        return 0.5  # neutral if template has no AcroForm fingerprint

    # Extract leaf names for both template and inspection results
    tmpl_leaf_names = {_leaf_name(n) for n in tmpl_acroform.get("field_names", [])}
    insp_leaf_names = {_leaf_name(n) for n in inspection.acroform_field_names}

    if not tmpl_leaf_names:
        return 0.5

    if not insp_leaf_names:
        return 0.0

    # Precision-oriented: fraction of template leaf names found in inspection
    overlap = len(tmpl_leaf_names & insp_leaf_names)
    precision = overlap / len(tmpl_leaf_names)

    return precision


def compute_page_structure_score(inspection: PDFInspectionResult, template: TemplateRecord) -> float:
    """
    Compare page count and page sizes against template page signature.
    """
    tmpl_sig = template.fingerprints.page_signature
    if not tmpl_sig:
        return 0.5

    score = 0.0

    # Page count match
    tmpl_page_count = tmpl_sig.get("page_count", 0)
    if tmpl_page_count > 0 and inspection.page_count == tmpl_page_count:
        score += 0.5

    # Page size match (check first page as proxy)
    tmpl_sizes = tmpl_sig.get("page_sizes", [])
    if tmpl_sizes and inspection.page_sizes:
        # Compare first page dimensions (with 1% tolerance)
        tmpl_w, tmpl_h = tmpl_sizes[0]
        insp_w, insp_h = inspection.page_sizes[0]
        if tmpl_w > 0 and tmpl_h > 0:
            w_ratio = min(tmpl_w, insp_w) / max(tmpl_w, insp_w)
            h_ratio = min(tmpl_h, insp_h) / max(tmpl_h, insp_h)
            if w_ratio > 0.99 and h_ratio > 0.99:
                score += 0.5

    return min(score, 1.0)


def compute_anchor_text_score(inspection: PDFInspectionResult, template: TemplateRecord) -> float:
    """
    Compare stable printed labels against template anchor text fingerprint.
    Matches phrases against:
    1. PDF metadata (title/subject — contains the form name)
    2. AcroForm field names (contains field labels)
    Uses partial word overlap for better matching.
    """
    tmpl_anchors = template.fingerprints.anchor_text
    if not tmpl_anchors or not tmpl_anchors.get("phrases"):
        return 0.5

    phrases = [p.lower() for p in tmpl_anchors.get("phrases", [])]
    if not phrases:
        return 0.5

    # Build searchable corpus: metadata values + field names
    searchable: list[str] = []
    searchable.extend(v.lower() for v in inspection.metadata.values() if isinstance(v, str))
    searchable.extend(name.lower().replace("_", " ").replace(".", " ") for name in inspection.acroform_field_names)

    matches = 0
    for phrase in phrases:
        phrase_words = set(phrase.split())
        if not phrase_words:
            continue
        matched = False
        for text in searchable:
            text_words = set(text.split())
            # Match if any phrase word appears in the searchable text
            if phrase_words & text_words:
                matched = True
                break
        if matched:
            matches += 1

    return min(matches / len(phrases), 1.0)


def compute_visual_anchor_score(inspection: PDFInspectionResult, template: TemplateRecord) -> float:
    """
    Placeholder for visual anchor scoring.
    Would compare page thumbnail hashes or anchor region hashes.
    For MVP, return neutral score.
    """
    tmpl_visual = template.fingerprints.visual_anchor
    if not tmpl_visual:
        return 0.5
    return 0.5  # TODO: implement thumbnail hashing


def compute_match_score(inspection: PDFInspectionResult, template: TemplateRecord) -> tuple[float, MatchSignals]:
    """
    Compute weighted final match score between a PDF inspection result
    and a registered template.
    """
    signals = MatchSignals(
        metadata_score=compute_metadata_score(inspection, template),
        acroform_score=compute_acroform_score(inspection, template),
        page_structure_score=compute_page_structure_score(inspection, template),
        anchor_text_score=compute_anchor_text_score(inspection, template),
        visual_anchor_score=compute_visual_anchor_score(inspection, template),
    )

    signals.final_score = (
        _WEIGHTS["metadata"] * signals.metadata_score
        + _WEIGHTS["acroform"] * signals.acroform_score
        + _WEIGHTS["page_structure"] * signals.page_structure_score
        + _WEIGHTS["anchor_text"] * signals.anchor_text_score
        + _WEIGHTS["visual_anchor"] * signals.visual_anchor_score
    )

    return signals.final_score, signals


def find_best_match(
    inspection: PDFInspectionResult,
    registry: TemplateRegistry,
) -> MatchResult:
    """
    Compare the PDF inspection against all active templates and return
    the best match if it exceeds the threshold, otherwise return unknown.
    """
    candidates = registry.list_active()

    if not candidates:
        return MatchResult(
            template_id=None,
            template_match_status="unknown",
            match_score=0.0,
        )

    best_score = 0.0
    best_template: Optional[TemplateRecord] = None

    for template in candidates:
        score, _ = compute_match_score(inspection, template)
        if score > best_score:
            best_score = score
            best_template = template

    if best_template and best_score >= TEMPLATE_MATCH_THRESHOLD:
        return MatchResult(
            template_id=best_template.template_id,
            template_match_status="matched",
            match_score=best_score,
        )

    # Fail-fast: unknown template
    return MatchResult(
        template_id=None,
        template_match_status="unknown",
        match_score=best_score,
    )
