# Confidence and Review Rules

## Locked MVP decisions

### 1. Final field confidence does not change after Gemma review
- GLM-OCR produces the primary handwritten extraction and its confidence score.
- If the field confidence is below `0.70`, Gemma4 e4b is invoked for review/refine on `http://127.0.0.1:11435`.
- Gemma review does **not** change the original field confidence score.
- The final field output keeps the original confidence from the primary extraction.

Example conceptual output:
- `value = "handwriting text"`
- `confidence = 0.70`
- `review = "handwriting text"`

This means the analyzer preserves the original primary-model confidence and attaches Gemma's review text separately.

---

### 2. Document-level review_required rule
- If **any single field** is low confidence, the whole document status becomes `review_required`.
- Low confidence means: `field.confidence < 0.70`

Document status rule:
- if any field has confidence `< 0.70` -> `status = review_required`
- otherwise -> normal completed flow applies

---

### 3. No per-field model provenance required in MVP
- The response does **not** need to explicitly record which model handled each field.
- Model provenance can be added later if needed.

---

## Intended MVP behavior

1. Run GLM-OCR on handwritten field using the dedicated endpoint `http://127.0.0.1:11436`
2. Record extracted text and confidence
3. If confidence >= 0.70:
   - keep field as normal
4. If confidence < 0.70:
   - call Gemma4 e4b for review/refine
   - store Gemma review text separately
   - keep original confidence unchanged
   - mark document as `review_required`
5. Build response using original confidence plus optional review text

---

## Notes
- This rule currently applies to handwritten fields.
- The threshold is fixed at `0.70` for MVP.
- Future versions may add richer confidence calibration or model provenance.
