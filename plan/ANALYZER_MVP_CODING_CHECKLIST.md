# Analyzer MVP Coding Checklist

This checklist translates the frozen MVP spec into implementation work items.

Primary reference:
- `FROZEN_MVP_SPEC_INDEX.md`

---

## 1. Project foundation
- [ ] Set up analyzer project structure for request handling, template loading, extraction, and response building
- [ ] Define config for local runtime paths and MLX server endpoints
- [ ] Add default Gemma endpoint config: `http://127.0.0.1:11435`
- [ ] Add default GLM-OCR endpoint config: `http://127.0.0.1:11436`
- [ ] Add configurable timeout and error handling for local model calls
- [ ] Document that one model is served per port in the MLX deployment layout
- [ ] Add setup step to download `mlx-community/GLM-OCR-bf16` locally before analyzer runtime testing

## 2. Request validation
- [ ] Validate incoming JSON request shape
- [ ] Validate `file.path` exists and is readable
- [ ] Validate file is a PDF
- [ ] Return contract-compliant `failed` response on invalid input

## 3. PDF inspection
- [ ] Read page count
- [ ] Detect basic PDF characteristics needed for template matching
- [ ] Detect AcroForm presence/field names when available
- [ ] Support empty-password decrypt for encrypted PDFs
- [ ] Return clear failure if encrypted PDF cannot be opened

## 4. Template registry
- [ ] Implement manifest-per-template registry loader
- [ ] Load template manifests from template folders
- [ ] Validate minimum manifest schema
- [ ] Validate minimum field schema format

## 5. Template matching
- [ ] Match PDFs against registered known templates
- [ ] Use page count, structural markers, AcroForm signals, and anchors for matching
- [ ] Return fail-fast response for unknown templates
- [ ] Return matched template metadata for downstream extraction

## 6. Page preprocessing and alignment
- [ ] Render PDF pages for analysis
- [ ] Add preprocessing needed for stable alignment
- [ ] Align document pages to template coordinates
- [ ] Produce alignment output usable by field cropper

## 7. Field extraction pipeline
- [ ] Load field definitions from matched template
- [ ] Map template coordinates to aligned document coordinates
- [ ] Crop field regions
- [ ] Route each field by declared field type

## 8. Handwritten extraction path
- [ ] Download `mlx-community/GLM-OCR-bf16` locally for MLX serving
- [ ] Serve `mlx-community/GLM-OCR-bf16` on dedicated MLX OpenAI-compatible endpoint `http://127.0.0.1:11436`
- [ ] Call `mlx-community/GLM-OCR-bf16` through the dedicated GLM-OCR endpoint
- [ ] Record extracted handwritten value
- [ ] Record original confidence from GLM-OCR
- [ ] If confidence `< 0.70`, call `Gemma4 e4b` on `http://127.0.0.1:11435` for review/refine
- [ ] Keep original GLM confidence unchanged
- [ ] Store Gemma review text separately in `review`

## 9. Non-handwritten field extraction
- [ ] Implement typed-text extraction path
- [ ] Implement checkbox extraction path
- [ ] Implement signature presence detection path
- [ ] Return contract-aligned field outputs for each field type

## 10. Validation and normalization
- [ ] Apply field-level validation rules
- [ ] Normalize extracted values into expected format
- [ ] Set `validation_status` per field
- [ ] Add warnings where needed

## 11. Review-required logic
- [ ] If any field has confidence `< 0.70`, set top-level status to `review_required`
- [ ] Otherwise return normal completed flow when extraction succeeds
- [ ] Preserve fail-fast behavior for unrecoverable request/template failures

## 12. Response builder
- [ ] Build top-level response matching frozen contract
- [ ] Build field objects using locked field response shape
- [ ] Support `completed`, `review_required`, and `failed` responses
- [ ] Keep `error` null unless whole request fails

## 13. Error handling
- [ ] Return structured error codes/messages for validation failures
- [ ] Return structured error codes/messages for unknown template failures
- [ ] Return structured error codes/messages for model/runtime failures
- [ ] Mark retryable vs non-retryable failures appropriately

## 14. Test coverage
- [ ] Add test for valid matched template flow
- [ ] Add test for low-confidence handwritten field causing `review_required`
- [ ] Add test for unknown template fail-fast behavior
- [ ] Add test for unreadable/missing file path
- [ ] Add test for encrypted PDF with empty-password decrypt
- [ ] Add test for encrypted PDF that cannot be opened
- [ ] Add test for response shape compliance

## 15. Implementation discipline
- [ ] Keep implementation aligned to `FROZEN_MVP_SPEC_INDEX.md`
- [ ] Do not add generic unknown-template extraction in MVP
- [ ] Do not add UI/review workflow features in MVP
- [ ] Do not add unnecessary model provenance fields in MVP
- [ ] Keep the implementation practical and minimal
