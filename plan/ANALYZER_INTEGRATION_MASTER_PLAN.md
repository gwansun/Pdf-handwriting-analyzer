# PDF Handwriting Analyzer - Integration Master Plan

## 1. Purpose

Define the PDF analyzer side of the system in a way that is concrete enough to integrate with Email Manager.

This plan assumes:
- Email Manager and PDF analyzer run on the same machine
- both systems share the same filesystem
- Email Manager saves PDF attachments locally
- Email Manager sends a JSON request containing local `file.path`

This document focuses on the analyzer as a worker system that receives a request, analyzes the PDF, and returns a structured JSON response.

---

## 2. Role of the Analyzer

The PDF analyzer is a downstream worker.

It does **not** own:
- email retrieval
- email filtering
- attachment download
- dashboard rendering

It **does** own:
- PDF intake validation
- template lookup and template registration logic
- page normalization and alignment
- field extraction
- OCR / handwriting extraction routing
- confidence scoring
- structured response generation

---

## 3. Integration Boundary with Email Manager

### Analyzer request comes from Email Manager
The analyzer receives:
- `request_id`
- `job_id`
- `email_id`
- `attachment_id`
- `file.path`
- surrounding email metadata
- execution options

### Analyzer response goes back to Email Manager
The analyzer returns:
- request/job identifiers
- status
- template match result
- field extraction results
- confidence scores
- warnings
- failure info if needed

### Source of truth for contract
Use the Email Manager document:
- `email-manager/plan/pdf-analyzer-api-contract.md`

This analyzer plan must stay aligned with that contract.

---

## 4. End-to-End Analyzer Runtime Flow

```text
Receive JSON request
  -> validate request
  -> read PDF from local file path
  -> inspect document type and metadata
  -> identify template
  -> if known template: reuse schema
  -> if unknown template: provisional template path or failure policy
  -> preprocess / align pages
  -> extract field regions
  -> classify field content types
  -> run extraction engines
  -> validate and normalize values
  -> score confidence
  -> assemble JSON response
  -> return to Email Manager
```

---

## 5. Analyzer Runtime Stages

## Stage 1. Request validation

### Input
JSON request from Email Manager.

### Required checks
- `request_id` exists
- `job_id` exists
- `file.path` exists
- file exists on disk
- file is readable
- MIME type or file extension indicates PDF

### Failure response
If validation fails, return:
- `status = failed`
- machine-readable error code
- human-readable message
- `retryable` flag

Example errors:
- `FILE_NOT_FOUND`
- `INVALID_REQUEST`
- `UNREADABLE_FILE`
- `NOT_A_PDF`

---

## Stage 2. PDF ingestion and inspection

### Goals
- confirm the file is a real PDF
- inspect basic PDF properties
- determine whether document is born-digital, scanned, or hybrid

### Output
- page count
- PDF metadata summary
- document type classification
- initial ingestion warnings if any

### Why this matters
This stage determines whether later extraction should prefer:
- native PDF text extraction,
- OCR on field crops,
- or mixed logic.

---

## Stage 3. Template identification

### Goal
Determine which known form template best matches the PDF.

### Inputs used for matching
- file metadata
- page count and page size
- native labels/anchors if present
- AcroForm fields if present
- structural signature
- visual anchors if necessary

### Possible outcomes
- `matched`: known template found with sufficient confidence
- `provisional`: weak match or partial template guess
- `unknown`: no suitable template

### MVP recommendation
For MVP:
- support `matched` and `unknown`
- allow `provisional` only if useful later

### Output
- `template_match_status`
- `template_id` or `null`

---

## Stage 4. Template loading

### If template is matched
- load template schema
- load field definitions
- load anchor definitions
- load runtime hints

### If template is unknown
Choose one of these policies:
1. fail fast and return `unknown template`, or
2. run provisional fallback analysis with low confidence

### MVP recommendation
Fail fast if unknown template handling is not yet robust.
That is safer than pretending extraction is reliable.

---

## Stage 5. Page preprocessing and alignment

### Goals
- render pages when needed
- denoise / deskew
- align each page to template coordinates
- compute alignment quality

### Output
- aligned page representation
- transform matrix per page
- alignment score per page

### Failure behavior
If alignment fails badly:
- either return failed job,
- or mark fields/page for review depending on severity.

### MVP recommendation
If page alignment fails for a template-dependent document, return failure or strong review warning.

---

## Stage 6. Field region extraction

### Goals
- use template field boxes
- map them onto aligned document pages
- crop field regions
- optionally crop context regions

### Output per field
- `field_name`
- crop image or reference
- page number
- bbox
- context bbox

---

## Stage 7. Field type routing

### Goal
Choose the correct extraction path for each field.

### Candidate classes
- empty
- typed
- handwritten
- mixed
- checkbox
- radio
- signature
- unknown

### Routing outputs
- extraction engine selected
- field type confidence

### Example routing logic
- native text present in bbox -> prefer direct/native extraction
- image-only field crop -> prefer OCR/handwriting extraction
- checkboxes/signatures -> specialized detector
- uncertain cases -> fallback multimodal reviewer

---

## Stage 8. Field extraction

### Possible extractor paths
- native PDF text extractor
- typed OCR extractor
- handwriting OCR extractor
- checkbox detector
- signature presence detector
- multimodal fallback

### Output per field
- extracted value
- candidates if available
- raw extractor confidence
- extraction metadata

### Important design rule
Preserve raw extractor output separately from final fused confidence.

---

## Stage 9. Validation and normalization

### Goals
- normalize values into standard forms
- validate against field-specific rules
- detect suspicious results

### Examples
- dates -> normalized date format
- numeric fields -> digit cleanup and range checks
- checkbox -> allowed values only
- names -> keep text, minimal normalization

### Output per field
- normalized value
- validation status
- warnings

---

## Stage 10. Confidence scoring

### Goal
Fuse multiple signals into final field confidence.

### Inputs
- extractor confidence
- image quality score
- alignment score
- validation score
- ambiguity gap
- optional consensus score

### Output per field
- `confidence`
- `review_required`
- optional `confidence_breakdown`

### Analyzer-level output
- `overall_confidence`
- document-level `review_required`

### Rule
Low confidence should not mean silent failure. It should become an explicit review signal.

---

## Stage 11. Response assembly

### Response must conform to contract
Return:
- `request_id`
- `job_id`
- `status`
- `summary`
- `fields`
- `warnings`
- optional `error`
- optional `raw_result`

### Status values
- `completed`
- `review_required`
- `failed`

### Rule
Even when extraction partially works, prefer returning a structured result over throwing away useful data.

---

## 6. Analyzer Module Design

### Module A. Request validator
Responsibilities:
- validate incoming JSON
- validate file existence/readability
- return normalized runtime request

### Module B. PDF inspector
Responsibilities:
- inspect PDF metadata
- count pages
- detect born-digital vs scanned vs hybrid

### Module C. Template matcher
Responsibilities:
- compute template fingerprints
- choose matched template or unknown

### Module D. Template registry
Responsibilities:
- load stored template schema
- provide fields, anchors, runtime hints

### Module E. Page alignment engine
Responsibilities:
- render page
- preprocess image
- align page to template

### Module F. Field cropper
Responsibilities:
- map template coordinates to document
- crop field and context regions

### Module G. Field router
Responsibilities:
- classify field content type
- choose extractor path

### Module H. Extractors
Submodules:
- native_text_extractor
- typed_ocr_extractor
- handwriting_extractor
- checkbox_extractor
- signature_extractor
- multimodal_fallback

### Module I. Validator / normalizer
Responsibilities:
- standardize values
- run field validation rules

### Module J. Confidence engine
Responsibilities:
- compute final confidence
- emit review flags and breakdowns

### Module K. Response builder
Responsibilities:
- format output to contract
- emit success/failure response

---

## 7. Request/Response Contract Mapping

## Request fields used by analyzer
From Email Manager request:
- `request_id` -> trace entire run
- `job_id` -> return unchanged
- `email_id` -> traceability only
- `attachment_id` -> traceability only
- `file.path` -> main PDF input
- `file.original_filename` -> logging / hints
- `context.sender` / `context.subject` -> optional context only
- `context.template_hint` -> optional template shortcut
- `options.*` -> response verbosity and mode control

## Response fields produced by analyzer
- `status` from analyzer run state
- `summary.template_match_status` from template matcher
- `summary.template_id` from template registry
- `summary.page_count` from PDF inspector
- `summary.overall_confidence` from confidence engine
- `summary.review_required` from document-level policy
- `fields[]` from field extraction pipeline
- `warnings[]` from any stage
- `error` from request, file, alignment, or extraction failure

---

## 8. Unknown Template Policy

This is one of the most important unfinished analyzer decisions.

### Option A. Fail fast
If template is unknown:
- return `failed` or `review_required`
- include `template_match_status = unknown`
- do not attempt unreliable extraction

### Option B. Provisional extraction
If template is unknown:
- try generic layout analysis
- return weaker confidence
- mark strong review requirement

### Recommendation
For MVP, prefer **Option A: fail fast**.
It is safer and easier to integrate with Email Manager.

---

## 9. Failure Modes

### Request/file failures
- missing file
- unreadable file
- non-PDF content

### Template failures
- no matching template
- template schema missing/corrupt

### Alignment failures
- page drift too large
- anchors not found

### Extraction failures
- crop unreadable
- OCR engine failure
- unsupported field type

### Response policy
All failures should map to structured error responses with:
- `code`
- `message`
- `retryable`

---

## 10. MVP Scope

### Must-have
- request validation
- PDF inspection
- known-template matching
- template loading
- alignment
- field crop extraction
- field extraction
- validation
- confidence scoring
- contract-compliant JSON response

### Can wait
- generic unknown-template extraction
- advanced calibration
- review UI artifacts
- annotated PDF overlays
- multi-pass consensus models

---

## 11. Acceptance Criteria

The analyzer side is ready for integration when:
- it accepts the defined JSON request
- it reads local PDF from `file.path`
- it returns contract-compliant JSON
- it handles missing/invalid files safely
- it handles unknown template cases predictably
- it returns field-level values and confidence for matched templates
- it returns structured failure output for non-processable documents

---

## 12. Recommended Next Documents

To finish analyzer-side planning, the next useful docs are:
1. analyzer internal module/task breakdown
2. template matching strategy spec
3. unknown-template policy spec
4. analyzer storage/runtime state design if persistence is needed

---

## 13. Final Recommendation

The analyzer should now be planned as a contract-driven worker:
- Email Manager owns files and jobs
- analyzer reads local PDF path
- analyzer returns structured JSON
- analyzer should be conservative when template certainty is low

That will keep the integration clean and reduce false confidence.