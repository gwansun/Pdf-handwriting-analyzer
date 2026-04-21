# Model Routing Decision

## Locked MVP decision

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
- If any field has **confidence < 0.70**, the analyzer must invoke **Gemma4 e4b** for review/refine on that field.

### Review/refine scope
- Gemma4 is used as a **secondary review/refine model**, not the default primary extractor.
- Gemma4 should be applied only to fields that fall below the confidence threshold.

---

## Intended MVP behavior

1. Extract field with GLM-OCR
2. Compute field confidence
3. If confidence >= 0.70:
   - accept primary result
4. If confidence < 0.70:
   - call Gemma4 e4b for review/refine
   - keep the original GLM-OCR `value`
   - attach Gemma review text separately in `review`
5. Return field value, confidence, review text when present, and any review-required flags in the analyzer response

---

## Notes
- This routing rule currently applies to handwritten field extraction.
- Additional routing rules for typed OCR, checkboxes, or signatures can be defined separately if needed.
- For MVP deployment, GLM-OCR and Gemma4 run on separate local ports:
  - GLM-OCR: `11436`
  - Gemma4: `11435`
- This document locks model selection, serving layout, and threshold behavior for MVP.
