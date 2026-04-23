# PDF Handwriting Analyzer - Frozen MVP Contract Spec

## 1. Purpose

Freeze the minimum JSON contract for the MVP integration between:
- Email Manager
- PDF Handwriting Analyzer

This document turns the earlier contract draft into the practical MVP boundary.

Anything not required here can be added later without blocking MVP.

---

## 2. MVP Contract Principle

For MVP, the contract should be:
- small
- stable
- easy to validate
- sufficient for matched-template extraction of known forms

Do not over-design optional fields in MVP.

---

## 3. Frozen MVP Request Schema

### Required top-level fields
```json
{
  "request_id": "string",
  "job_id": "string",
  "attachment_id": "string",
  "file": {
    "path": "string"
  }
}
```

### Supported optional fields
```json
{
  "email_id": "string",
  "file": {
    "original_filename": "string",
    "saved_filename": "string",
    "mime_type": "application/pdf",
    "size_bytes": 12345,
    "checksum": "sha256:..."
  },
  "context": {
    "received_date": "YYYY-MM-DD",
    "sender": "string",
    "subject": "string",
    "language_hint": "en",
    "template_hint": "string or null"
  },
  "options": {
    "return_field_candidates": true,
    "return_confidence_breakdown": true,
    "mode": "default"
  }
}
```

---

## 4. Frozen MVP Request Rules

### Required
- `request_id`
- `job_id`
- `attachment_id`
- `file.path`

### Required assumptions
- `file.path` points to a local readable PDF on the shared filesystem
- both systems are on the same machine for MVP

### Optional but recommended
- `context.template_hint`
- `file.original_filename`
- `file.mime_type`

---

## 5. Frozen MVP Response Schema

### Required top-level fields
```json
{
  "request_id": "string",
  "job_id": "string",
  "status": "completed | review_required | failed"
}
```

### If `status = completed` or `review_required`
Response must include:
```json
{
  "summary": {
    "template_match_status": "matched | unknown",
    "template_id": "string or null",
    "page_count": 3,
    "overall_confidence": 0.91,
    "review_required": false,
    "warning_count": 0,
    "field_count": 4
  },
  "fields": []
}
```

### If `status = failed`
Response must include:
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "retryable": true
  }
}
```

---

## 6. Frozen MVP Field Object

Each field object must include:

```json
{
  "field_name": "string",
  "field_label": "string",
  "field_type": "string",
  "value": "string or null",
  "confidence": 0.90,
  "validation_status": "valid | uncertain | invalid",
  "review_required": false,
  "warnings": [],
  "bbox": [0, 0, 0, 0]
}
```

### Important MVP rule
For handwritten fields:
- keep the original form field identity
- return interpreted handwritten text in `value`
- return confidence for that interpreted value in `confidence`

Example:
```json
{
  "field_name": "employee_first_name",
  "field_label": "First name",
  "field_type": "handwritten_name",
  "value": "Leonardo",
  "confidence": 0.90,
  "validation_status": "valid",
  "review_required": false,
  "warnings": [],
  "bbox": [540, 320, 880, 395]
}
```

---

## 7. Optional MVP Response Fields

These are allowed but not mandatory for MVP:
- `warnings` (document-level)
- `raw_result`
- `candidates`
- `confidence_breakdown`

### Rule
Email Manager should tolerate these fields if present, but not require them to begin integration.

---

## 8. Frozen MVP Status Meanings

### `completed`
- matched template
- extraction usable
- no strong review warning required

### `review_required`
- extraction usable
- but one or more fields are uncertain
- user should review low-confidence document results

### `failed`
- request invalid, file unreadable, template unknown, or extraction could not proceed safely

---

## 9. Frozen MVP Error Codes

Recommended MVP error codes:
- `INVALID_REQUEST`
- `FILE_NOT_FOUND`
- `UNREADABLE_FILE`
- `NOT_A_PDF`
- `UNSUPPORTED_ENCRYPTION`
- `UNKNOWN_TEMPLATE`
- `TEMPLATE_SCHEMA_LOAD_FAILED`
- `ALIGNMENT_FAILED`
- `EXTRACTION_FAILED`

These do not need to be exhaustive yet.

---

## 10. Frozen MVP Summary Rules

### `template_match_status`
For MVP, use only:
- `matched`
- `unknown`

### `template_id`
- required if matched
- `null` if unknown

### `overall_confidence`
- required for `completed` and `review_required`
- may be `0.0` for `failed`

---

## 11. Backward/Forward Compatibility Rule

For MVP:
- analyzer must always return required fields
- Email Manager must ignore unknown extra fields
- optional fields can be added later without breaking the contract

---

## 12. Final MVP Freeze

This is the locked MVP boundary:
- local file path in request
- minimal required IDs
- 3 statuses only
- field objects with `value + confidence`
- handwritten values returned as interpreted text
- structured error object on failure

This is enough for both systems to build independently now.
