# Field Response Shape Decision

## Locked decision

For handwritten fields, the analyzer response should keep the primary first-pass extraction result and attach Gemma review output separately when document-level review is triggered.

Gemma review output may come from either:
- **matched-template review**
- **fallback review** when manifest/schema metadata is unavailable

---

## Field shape

Recommended MVP field structure:

```json
{
  "field_name": "employee_name",
  "label": "Employee Name",
  "type": "handwritten_text",
  "value": "John Smith",
  "confidence": 0.62,
  "validation_status": "valid",
  "bbox": { "x": 120, "y": 340, "w": 220, "h": 42 },
  "review": "John Smith",
  "warnings": []
}
```

---

## Locked meaning of each field

- `value`
  - The primary first-pass extraction result from GLM-OCR (or other primary extraction route)
- `confidence`
  - The original first-pass confidence score
- `review`
  - Gemma review/refine text when document-level review is triggered and Gemma provides a reviewed result for this field
  - this review output may come from either matched-template review or fallback review mode
  - `null` when no review is triggered or when Gemma does not revise that field
- `validation_status`
  - Validation outcome for the field
- `bbox`
  - Bounding box for the field region
- `warnings`
  - Optional warning list

---

## Review trigger behavior

### Normal-confidence document
If average document confidence is `>= 0.70`:

```json
{
  "field_name": "employee_name",
  "type": "handwritten_text",
  "value": "John Smith",
  "confidence": 0.84,
  "review": null
}
```

### Low-confidence document
If average document confidence is `< 0.70`, the document enters the Gemma whole-PDF review path.
A reviewed field may then look like:

```json
{
  "field_name": "employee_name",
  "type": "handwritten_text",
  "value": "J0hn Smith",
  "confidence": 0.62,
  "review": "John Smith"
}
```

---

## Locked interpretation

### Chosen MVP option
- `value` remains the raw primary first-pass extraction result
- `review` contains Gemma's reviewed/refined text

This means the analyzer does **not** silently overwrite the primary extraction result.

---

## Document-level rule
- If average document confidence is `< 0.70`, the top-level document status becomes `review_required`.
- Gemma is called **once for the document**, not once per field.
- Gemma review should still be available even when manifest/schema metadata is missing.

---

## Notes
- This is intentionally minimal for MVP.
- No per-field model provenance is required.
- More structured review payloads such as `review_reasoning` or `review_confidence` can be added later if needed.
- Detailed implementation plan: `IMPLEMENTATION_PLAN_GEMMA_WHOLE_PDF_REVIEW.md`
