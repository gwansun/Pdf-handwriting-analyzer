# Field Response Shape Decision

## Locked MVP decision

For handwritten fields, the analyzer response should keep the primary extraction result and attach Gemma review text separately when review is triggered.

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
  - The primary extraction result from GLM-OCR
- `confidence`
  - The original confidence score from GLM-OCR
- `review`
  - Gemma review/refine text when confidence is below threshold
  - `null` when no review is triggered
- `validation_status`
  - Validation outcome for the field
- `bbox`
  - Bounding box for the field region
- `warnings`
  - Optional warning list

---

## Review trigger behavior

### Normal-confidence field
If `confidence >= 0.70`:

```json
{
  "field_name": "employee_name",
  "type": "handwritten_text",
  "value": "John Smith",
  "confidence": 0.84,
  "review": null
}
```

### Low-confidence field
If `confidence < 0.70`:

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
- `value` remains the raw primary extraction from GLM-OCR
- `review` contains Gemma's review/refine text

This means the analyzer does **not** silently overwrite the primary extraction result.

---

## Document-level rule
- If any field has `confidence < 0.70`, the top-level document status becomes `review_required`.

---

## Notes
- This is intentionally minimal for MVP.
- No per-field model provenance is required.
- More structured review payloads can be added later if needed.
