# Top-Level Response Example

## Locked MVP response example

This document provides a concrete top-level analyzer response shape for MVP.

---

## Example: review_required response

```json
{
  "status": "review_required",
  "summary": {
    "template_match_status": "matched",
    "template_id": "t2200_v1",
    "page_count": 3,
    "overall_confidence": 0.78,
    "review_required": true,
    "field_count": 4
  },
  "fields": [
    {
      "field_name": "employee_name",
      "label": "Employee Name",
      "type": "handwritten_text",
      "value": "J0hn Smith",
      "confidence": 0.62,
      "validation_status": "review_required",
      "bbox": { "x": 120, "y": 340, "w": 220, "h": 42 },
      "review": "John Smith",
      "warnings": []
    },
    {
      "field_name": "tax_year",
      "label": "Tax Year",
      "type": "typed_text",
      "value": "2025",
      "confidence": 0.98,
      "validation_status": "valid",
      "bbox": { "x": 440, "y": 120, "w": 80, "h": 28 },
      "review": null,
      "warnings": []
    },
    {
      "field_name": "checkbox_remote_work",
      "label": "Remote Work",
      "type": "checkbox",
      "value": "checked",
      "confidence": 0.95,
      "validation_status": "valid",
      "bbox": { "x": 250, "y": 510, "w": 18, "h": 18 },
      "review": null,
      "warnings": []
    },
    {
      "field_name": "employer_signature",
      "label": "Employer Signature",
      "type": "signature",
      "value": "present",
      "confidence": 0.89,
      "validation_status": "valid",
      "bbox": { "x": 110, "y": 690, "w": 180, "h": 60 },
      "review": null,
      "warnings": []
    }
  ],
  "error": null
}
```

---

## Example: completed response

```json
{
  "status": "completed",
  "summary": {
    "template_match_status": "matched",
    "template_id": "t2200_v1",
    "page_count": 3,
    "overall_confidence": 0.93,
    "review_required": false,
    "field_count": 4
  },
  "fields": [
    {
      "field_name": "employee_name",
      "label": "Employee Name",
      "type": "handwritten_text",
      "value": "John Smith",
      "confidence": 0.82,
      "validation_status": "valid",
      "bbox": { "x": 120, "y": 340, "w": 220, "h": 42 },
      "review": null,
      "warnings": []
    }
  ],
  "error": null
}
```

---

## Example: failed response

```json
{
  "status": "failed",
  "summary": {
    "template_match_status": "unknown",
    "template_id": null,
    "page_count": 3,
    "overall_confidence": 0.0,
    "review_required": false,
    "field_count": 0
  },
  "fields": [],
  "error": {
    "code": "unknown_template",
    "message": "No registered template matched this PDF.",
    "retryable": false
  }
}
```

---

## Locked rules reflected here
- `status` is one of: `completed`, `review_required`, `failed`
- if average document confidence is `< 0.70`, top-level `status` becomes `review_required`
- Gemma review may run in either matched-template mode or fallback mode when schema/manifest is unavailable
- `value` keeps the primary GLM-OCR output for handwritten fields
- `review` stores Gemma review text when triggered
- `error` is `null` unless the whole request fails

---

## Notes
- `overall_confidence` can be computed separately from individual field confidence, but should remain simple in MVP.
- Model serving layout for MVP:
  - GLM-OCR endpoint: `http://127.0.0.1:11436`
  - Gemma4 review endpoint: `http://127.0.0.1:11435`
- This document is meant to keep implementation and downstream integration aligned.
