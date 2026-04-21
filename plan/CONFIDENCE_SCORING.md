# PDF Handwriting Analyzer - Confidence Scoring Plan

## 1. Purpose

Define how the system assigns a field-level confidence score in the range `0.0 - 1.0` for extracted values.

The confidence score should reflect how trustworthy the extracted field value is, based on multiple evidence signals rather than a single OCR engine output.

---

## 2. Design Principles

Confidence scoring should be:
- field-level, not only document-level
- evidence-based
- explainable
- calibrated over time
- conservative when uncertainty is high
- suitable for threshold-based human review

---

## 3. Why Single-Source Confidence Is Not Enough

A raw OCR confidence number alone is usually insufficient because:
- OCR engines may overestimate confidence
- handwriting models can be confidently wrong
- alignment issues can corrupt extraction silently
- partial clipping may not be reflected in token confidence
- semantically invalid values may still have high recognition confidence

Therefore, final confidence should be a fused score from multiple signals.

---

## 4. Confidence Layers

### Layer A. Extraction Confidence
Signals directly produced by OCR or multimodal extraction.

Examples:
- token-level OCR confidence
- average character confidence
- model logprob proxy if available
- best-vs-second-best candidate gap

### Layer B. Image / Crop Quality Confidence
Signals related to visual quality of the field region.

Examples:
- blur score
- contrast score
- noise level
- resolution adequacy
- clipping / truncation detection
- field occupancy ratio

### Layer C. Alignment Confidence
Signals related to page-to-template registration quality.

Examples:
- anchor match score
- transform residual error
- geometric overlap score
- field boundary agreement

### Layer D. Validation Confidence
Signals related to whether the extracted value makes sense.

Examples:
- regex/pattern match success
- allowed value match
- date validity
- numeric range validity
- semantic compatibility with nearby fields

### Layer E. Consensus Confidence
Signals related to agreement across extractors or passes.

Examples:
- typed OCR and VLM agree
- two extraction passes produce same result
- handwriting extractor candidates converge

---

## 5. Proposed Confidence Factors

Each field result may include the following normalized signals:

- `extractor_confidence`
- `candidate_margin_score`
- `image_quality_score`
- `alignment_score`
- `pattern_validation_score`
- `semantic_consistency_score`
- `consensus_score`
- `field_type_classification_score`
- `empty_field_score`

All factors should be normalized to `0.0 - 1.0`.

---

## 6. Initial Scoring Strategy

A practical MVP strategy is weighted fusion.

Example:

```text
final_confidence =
  0.30 * extractor_confidence +
  0.10 * candidate_margin_score +
  0.15 * image_quality_score +
  0.15 * alignment_score +
  0.15 * pattern_validation_score +
  0.10 * semantic_consistency_score +
  0.05 * consensus_score
```

This is not final truth, just an initial scoring baseline.

Weights should vary by field type over time.

---

## 7. Field-Type-Specific Confidence Logic

### 7.1 Typed text fields
Important signals:
- OCR token confidence
- pattern validation
- alignment quality

### 7.2 Handwritten text fields
Important signals:
- handwriting extractor confidence
- image quality
- candidate ambiguity gap
- semantic/pattern checks

### 7.3 Date fields
Important signals:
- extraction confidence
- strict date validity
- cross-field consistency if relevant

### 7.4 Checkbox / radio fields
Important signals:
- mark-detection confidence
- neighboring box separation quality
- image contrast

### 7.5 Signature fields
Confidence may mean:
- confidence that a signature is present
- not confidence in text recognition

---

## 8. Confidence Output Structure

Suggested per-field confidence object:

```json
{
  "field_name": "patient_name",
  "value": "John Smith",
  "confidence": 0.87,
  "review_required": false,
  "confidence_breakdown": {
    "extractor_confidence": 0.83,
    "candidate_margin_score": 0.78,
    "image_quality_score": 0.92,
    "alignment_score": 0.95,
    "pattern_validation_score": 0.85,
    "semantic_consistency_score": 0.88,
    "consensus_score": 0.80
  },
  "warnings": []
}
```

---

## 9. Review Threshold Policy

Suggested default thresholds:

- `0.95 - 1.00`: very high confidence
- `0.80 - 0.94`: acceptable / likely correct
- `0.60 - 0.79`: review recommended
- `< 0.60`: review required

These thresholds should be configurable.

---

## 10. Special Cases

### Empty vs unreadable
The system should distinguish:
- intentionally empty
- probably empty
- unreadable but not clearly empty

### Partial clipping
If the field content is near crop boundaries:
- penalize confidence
- emit warning

### Ambiguous candidates
If multiple candidates are similar:
- reduce confidence
- preserve alternatives if possible

### Invalid but readable values
If a value is clearly readable but fails business validation:
- preserve extracted text
- reduce trust score
- mark validation warning rather than pretending OCR failed

---

## 11. Calibration Strategy

Over time, confidence should be calibrated using labeled data.

Recommended approach:
- collect human-reviewed extraction results
- compare predicted confidence to actual correctness
- calibrate weights and thresholds
- potentially train a separate confidence model

---

## 12. Explainability Requirements

Every confidence result should be explainable.

At minimum, the system should be able to answer:
- why confidence was low
- which signals contributed most
- whether the issue was image quality, alignment, ambiguity, or validation

---

## 13. MVP Recommendation

For MVP, use:
- weighted confidence fusion
- small number of signals
- simple threshold rules
- confidence breakdown in output
- review flags based on thresholds

Do not overcomplicate with advanced calibration until labeled data exists.

---

## 14. Future Directions

- field-type-specific learned confidence models
- calibration curves
- uncertainty estimation with ensemble extraction
- user feedback loop for confidence refinement
- document-level risk scoring derived from field confidences
