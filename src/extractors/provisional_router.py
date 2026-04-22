"""
Module T8: Provisional Router
Field-level extraction logic for unknown filled PDFs without a schema-driven
matched-template flow.

Provides best-effort extraction that:
- Does NOT require a schema
- Can produce zero fields or sparse fields
- Always produces low-confidence results
- Is schema-free (no template lookup required)

This is NOT a template-matching path — it is pure content extraction
without any template knowledge.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("provisional_router")


@dataclass
class ProvisionalFieldResult:
    field_name: str
    value: Optional[str]
    confidence: float
    field_type: str
    bbox: list
    warnings: list[str]


def extract_provisional_fields(
    pdf_path: str,
    page_sizes: list[tuple],
    glm_available: bool = True,
) -> list[ ProvisionalFieldResult]:
    """
    Perform best-effort field extraction on an unknown PDF without a schema.

    For MVP, this extracts no structured fields — the document is treated
    as an unknown form with no predefined schema. The fallback response
    will return an empty field list with low overall confidence.

    In post-MVP, this could implement:
    - heuristic field detection (labeled regions, table structures)
    - generic OCR pass over all pages
    - layout analysis to detect form-like regions

    Returns
    -------
    list[ProvisionalFieldResult]
        Extracted fields (empty for MVP).
    """
    # MVP: no schema-free field detection implemented
    # The unknown_fallback module will handle the response semantics
    return []


def estimate_overall_confidence(field_results: list[ProvisionalFieldResult]) -> float:
    """
    Estimate overall document confidence from provisional field results.
    For MVP with no fields, returns a conservative low value.
    """
    if not field_results:
        return 0.20
    total = sum(r.confidence for r in field_results)
    return round(total / len(field_results), 3)
