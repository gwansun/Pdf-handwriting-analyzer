"""
Confidence scorer: computes document-level confidence from field results.
"""
from typing import Optional

def compute_document_confidence(
    field_results: list,
    review_threshold: float = 0.70,
) -> tuple[float, bool, int]:
    """
    Compute overall document confidence from field extractions.
    Returns (avg_confidence, review_required, low_confidence_count).
    """
    if not field_results:
        return 0.0, True, 0

    confidences = [f.confidence for f in field_results if hasattr(f, 'confidence')]
    if not confidences:
        return 0.0, True, 0

    avg_conf = sum(confidences) / len(confidences)
    low_conf_count = sum(1 for c in confidences if c < review_threshold)
    review_required = avg_conf < review_threshold or low_conf_count > 0

    return avg_conf, review_required, low_conf_count