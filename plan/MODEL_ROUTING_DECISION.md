# Model Routing Decision

## Locked decision

### Primary handwriting extraction model
- **Model:** `mlx-community/GLM-OCR-bf16`
- **Serving:** dedicated `mlx-vlm` server instance
- **Endpoint style:** local HTTP endpoint
- **Default local endpoint:** `http://127.0.0.1:11436`
- **Deployment note:** the GLM-OCR model must be downloaded locally and served on its own port because only one model can be served per port

### Review / refine model
- **Model:** `Gemma4 e4b`
- **Serving:** separate model server instance
- **Endpoint style:** local OpenAI-compatible HTTP endpoint
- **Default local endpoint:** `http://127.0.0.1:11435`

---

## Routing rule

### Default path
- All handwritten fields are first processed by **GLM-OCR**.

### Review/refine trigger
- If **any extracted field** is marked `review_required`, the analyzer should invoke **Gemma4 e4b once for the whole PDF**.

### Review/refine scope
- Gemma4 is used as a **secondary document-level review/refine model**, not the default primary extractor.
- Gemma4 should **not** be called once per low-confidence field.
- Gemma4 review should work in two modes:
  1. **matched-template review**
  2. **fallback review without manifest/schema metadata**

### Matched-template review payload
When template metadata exists, Gemma should receive:
- manifest/runtime hints
- full schema
- first-pass extracted field values
- document confidence summary
- review target field list

### Fallback review payload
When manifest/schema metadata does **not** exist, Gemma should still receive:
- PDF/document metadata
- page count
- inspection signals
- provisional extraction results if available
- AcroForm values if available
- page text snippets if available
- document confidence summary
- document classification / warning context

---

## Intended behavior

1. Extract handwritten fields with GLM-OCR
2. Compute field confidence for all fields
3. Mark field-level `review_required` during first-pass extraction/fallback logic
4. If no fields are marked `review_required`:
   - accept first-pass results
5. If any field is marked `review_required`:
   - call Gemma4 e4b **once** for the whole PDF
   - if template metadata exists, use matched-template review payload
   - if template metadata does not exist, use fallback review payload
   - keep the original first-pass field `value`
   - attach Gemma review output separately in `review`
6. Return field value, confidence, review text when present, and document-level `review_required` when triggered

---

## Notes
- This routing rule currently applies to handwritten-field review and any other field types that set `review_required` during extraction.
- Additional routing rules for typed OCR, checkboxes, or signatures can be defined separately if needed.
- For deployment, GLM-OCR and Gemma4 run on separate local ports:
  - GLM-OCR: `11436`
  - Gemma4: `11435`
- This document locks model selection, serving layout, and review scope behavior.
- Detailed implementation plan: `IMPLEMENTATION_PLAN_GEMMA_WHOLE_PDF_REVIEW.md`
