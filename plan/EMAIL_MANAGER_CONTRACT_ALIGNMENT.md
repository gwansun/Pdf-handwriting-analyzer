# PDF Handwriting Analyzer - Email Manager Contract Alignment

## 1. Purpose

Summarize exactly how the PDF analyzer should align to the Email Manager integration contract.

---

## 2. Shared Deployment Assumption

- both systems run on the same machine
- both systems share the same filesystem
- Email Manager saves PDF first
- analyzer reads from local `file.path`

This is the approved MVP design.

---

## 3. Input Contract Expectations

The analyzer should expect a request shaped like:
- `request_id`
- `job_id`
- `email_id`
- `attachment_id`
- `file.path`
- `file.original_filename`
- `file.saved_filename`
- `file.mime_type`
- `file.size_bytes`
- optional `file.checksum`
- `context.*`
- `options.*`

### Minimum required fields for MVP
- `request_id`
- `job_id`
- `attachment_id`
- `file.path`

---

## 4. Output Contract Expectations

The analyzer should return:
- `request_id`
- `job_id`
- `status`
- `summary`
- `fields`
- optional `warnings`
- optional `error`
- optional `raw_result`

### Status values
- `completed`
- `review_required`
- `failed`

---

## 5. Email Manager Expectations From Analyzer

Email Manager expects the analyzer to be:
- deterministic in response shape
- conservative when uncertain
- explicit about failure reasons
- stable even as internals evolve

### Important rule
The analyzer may change its internal extraction logic later, but it should keep the contract stable.

---

## 6. Recommended Analyzer Response Policy

### If matched template and usable extraction
- return `completed`
- include extracted fields and confidence

### If extraction partially works but needs caution
- return `review_required`
- include fields and warnings

### If document cannot be processed safely
- return `failed`
- include structured error object

---

## 7. Final Recommendation

Treat the Email Manager contract as the public boundary.

Inside the analyzer, anything can evolve.
At the boundary, keep the request/response stable.
