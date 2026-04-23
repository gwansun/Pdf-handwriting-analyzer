# Confidence and Review Rules

## Locked decisions

### 1. Final field confidence remains the first-pass confidence
- GLM-OCR produces the primary handwritten extraction and its confidence score.
- Gemma4 e4b is used as a **document-level review/refine pass** when review is triggered.
- Gemma review does **not** change the original first-pass confidence score by default.
- The final field output keeps the original primary confidence unless a future product decision explicitly changes that behavior.

Example conceptual output:
- `value = "handwriting text"`
- `confidence = 0.62`
- `review = "reviewed handwriting text"`

This means the analyzer preserves the original primary-model confidence and attaches Gemma's review output separately.

---

### 2. Document-level Gemma trigger rule
- Gemma review is triggered when **any field** is marked `review_required`.
- This is a **field-driven trigger** with a **document-level single review call**.
- Trigger rule: `any(fr.review_required for fr in field_results)`
- This rule applies whether or not manifest/schema metadata exists.

Document review trigger rule:
- if no fields are marked `review_required` -> no Gemma review pass
- if any field is marked `review_required` -> call Gemma **once** for the whole PDF

---

### 3. Review should not depend on manifest/schema availability
- Matched-template metadata should improve Gemma review quality when available.
- But missing manifest/schema metadata must **not** block Gemma review.
- If the PDF is unmatched or schema is unavailable, the analyzer should still build a fallback Gemma review payload using available document signals.

---

### 4. Document-level final `review_required` rule
- If any field is marked `review_required`, the top-level document status becomes `review_required`.

Document status rule:
- if any field is `review_required` -> `status = review_required`
- otherwise -> normal completed flow applies

---

### 5. No per-field model provenance required in MVP
- The response does **not** need to explicitly record which model handled each field.
- Model provenance can be added later if needed.

---

## Intended behavior

1. Run GLM-OCR on handwritten fields using the dedicated endpoint `http://127.0.0.1:11436`
2. Record extracted text and first-pass confidence for all fields
3. Mark field-level `review_required` during extraction/fallback logic
4. If no fields are marked `review_required`:
   - keep normal completed flow
5. If any field is marked `review_required`:
   - call Gemma4 e4b **once** for the whole PDF
   - if template metadata exists, provide full matched-template context:
     - manifest/runtime hints
     - full schema
     - first-pass extraction results
     - document confidence summary
     - review target field list
   - if template metadata does not exist, provide fallback review context:
     - PDF metadata
     - page count
     - inspection signals
     - provisional extraction results if available
     - AcroForm/page text signals if available
   - store Gemma review text separately
   - keep original first-pass confidence unchanged
   - mark document as `review_required`
6. Build response using original confidence plus optional review output

---

## Notes
- This rule currently applies to handwritten-field review and any other extracted field types that set `review_required`.
- The threshold `0.70` still matters indirectly because field extractors may use it when deciding whether a field should be marked `review_required`.
- Future versions may add richer confidence calibration, model provenance, or a policy for promoting reviewed values into the main `value` field.
- Detailed implementation plan: `IMPLEMENTATION_PLAN_GEMMA_WHOLE_PDF_REVIEW.md`
