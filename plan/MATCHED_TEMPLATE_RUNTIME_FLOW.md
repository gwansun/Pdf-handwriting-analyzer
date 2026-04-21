# PDF Handwriting Analyzer - Matched Template Runtime Flow

## 1. Purpose

Define the exact runtime flow the analyzer should follow after an incoming PDF has been matched to a known template.

This is the most important analyzer execution path for MVP.

---

## 2. Scope

This document covers only the **matched-template path**.

It assumes:
- request has already been validated
- input file exists and is readable
- template matching has already succeeded
- a template manifest and schema can be loaded

This document does **not** define the unknown-template fallback path.

---

## 3. Goal

Given:
- a saved filled PDF,
- a matched template,
- a template schema,

The analyzer should:
1. load the template assets,
2. align the filled PDF to template coordinates,
3. extract field regions,
4. choose the right extraction route per field,
5. validate and score results,
6. return structured JSON.

---

## 4. End-to-End Runtime Flow

```text
Validated request
  -> matched template id
  -> load template manifest + schema
  -> inspect PDF pages
  -> align each page to template
  -> map schema fields onto aligned pages
  -> crop field regions
  -> route each field to extraction path
  -> extract values
  -> normalize and validate values
  -> compute field confidence
  -> compute document-level review flag
  -> assemble contract response
```

---

## 5. Runtime Stages

## Stage 1. Load template assets

### Inputs
- `template_id`
- template manifest
- schema reference

### Actions
- load manifest JSON
- load template schema
- load anchors if separate
- load runtime hints

### Outputs
- template definition in memory
- field list
- page definitions
- runtime hints

### Failure behavior
If the template exists in registry but schema cannot be loaded:
- return `failed`
- error code such as `TEMPLATE_SCHEMA_LOAD_FAILED`

---

## Stage 2. Inspect runtime document pages

### Goals
- inspect actual page count
- confirm page order and dimensions
- confirm document is consistent with matched template expectations

### Checks
- page count matches template or acceptable variant
- page sizes are within tolerance
- document encryption/readability is okay

### Failure behavior
If the document is structurally inconsistent with the matched template:
- either fail early,
- or downgrade confidence and continue only if safe

### MVP recommendation
Fail early on strong structural mismatch.

---

## Stage 3. Align pages to template

### Goal
Map each filled PDF page to the corresponding template page coordinate system.

### Inputs
- template page geometry
- anchors from template
- runtime PDF page rendering

### Actions
- render page to image if needed
- run preprocessing
- locate anchors / lines / boxes / labels
- estimate transform matrix
- score alignment quality

### Outputs
- aligned page representation
- page transform matrix
- alignment quality score

### Rule
Alignment quality should be preserved as an explicit signal for later confidence scoring.

---

## Stage 4. Resolve field coordinates

### Goal
Take template schema bboxes and map them onto aligned document pages.

### Actions
- iterate schema fields
- select page number
- transform template bbox into runtime coordinates
- compute optional context bbox

### Outputs
Per field:
- field name
- page number
- aligned bbox
- context bbox

---

## Stage 5. Crop field regions

### Goal
Create extraction-ready inputs for each field.

### Actions
- crop the exact field bbox
- optionally crop larger context region
- store crop metadata

### Outputs per field
- field crop image or extractable region
- context crop
- crop quality notes

### Note
The crop stage should not yet decide extraction route. It should prepare clean inputs first.

---

## Stage 6. Route field to extraction path

### Goal
Choose the best extraction strategy for each field.

### Inputs
- template field definition
- runtime hints
- crop content cues
- native PDF text availability

### Possible routes
- native text extraction
- typed OCR
- handwriting OCR
- checkbox detector
- signature detector
- multimodal fallback

### Routing factors
- field type from schema
- input mode from schema
- presence of native text in field bbox
- visual field content type
- document class (born-digital / scanned / hybrid)

### Output per field
- selected route
- route confidence or explanation

---

## Stage 7. Extract field value

### Goal
Run the chosen extractor and gather raw candidates.

### Outputs per field
- raw extracted value
- interpreted field value
- alternate candidates if available
- extractor confidence
- extraction method used

### Important rule
Keep extraction confidence separate from final confidence.

### Handwritten field rule
For handwritten fields, the analyzer should preserve the same schema field identity but return the interpreted handwritten text as the field value.

Example:
- schema field: `employee_name`
- extracted value: `Leonardo Romero`
- confidence: `0.90`

This applies to handwritten fields broadly, not only signatures.

---

## Stage 8. Normalize and validate

### Goal
Convert raw extracted values into stable output values and validation status.

### Actions
- normalize whitespace
- normalize date/number formats
- validate against field rules
- attach warnings

### Output per field
- normalized value
- validation status
- warning list

---

## Stage 9. Compute final field confidence

### Goal
Fuse runtime signals into final field confidence.

### Inputs
- extractor confidence
- image quality
- alignment score
- validation score
- ambiguity/candidate margin
- field type routing confidence

### Outputs per field
- final confidence
- review_required flag
- optional confidence breakdown

---

## Stage 10. Compute document-level summary

### Goal
Produce top-level analyzer result summary.

### Inputs
- template match result
- field results
- warning counts
- low-confidence counts

### Outputs
- page count
- overall confidence
- review_required
- field count
- warning count

### Recommended policy
If one or more critical fields are low confidence, mark document `review_required`.

---

## Stage 11. Build response

### Goal
Return contract-compliant JSON to Email Manager.

### Must include
- `request_id`
- `job_id`
- `status`
- `summary`
- `fields`

### Optional
- `warnings`
- `raw_result`
- `candidates`
- `confidence_breakdown`

### Status rule
- if extraction is usable -> `completed`
- if extraction is usable but caution is needed -> `review_required`
- if matched-template path fails critically -> `failed`

---

## 6. Recommended Runtime Field Object

Internal runtime field object should carry at least:
- `field_name`
- `field_label`
- `field_type`
- `page_number`
- `bbox`
- `context_bbox`
- `route`
- `raw_value`
- `interpreted_value`
- `normalized_value`
- `extractor_confidence`
- `final_confidence`
- `validation_status`
- `warnings`
- `review_required`

This makes later response building easier.

---

## 7. T2200 Example Fit

For T2200-style fillable PDFs, the matched-template path is especially suitable because:
- AcroForm fingerprint can identify the template strongly
- known fields like `Last_Name_Fill` and `Tax_Year_Fill` can map directly into schema definitions
- some fields may support native/form extraction before OCR is needed

This means matched-template runtime can often be faster and more reliable than generic document analysis.

---

## 8. MVP Recommendation

For MVP, prioritize this exact matched-template path:
1. load manifest/schema
2. inspect page structure
3. align pages
4. map field bboxes
5. crop field regions
6. route extraction per field
7. normalize and validate
8. compute confidence
9. return structured JSON

This is the core production path for known forms.

---

## 9. Final Recommendation

The analyzer should be optimized around matched-template execution first.

Why:
- it is the safest path
- it fits the Email Manager integration cleanly
- it works well with forms like the T2200 example
- it provides a realistic MVP before unknown-template handling becomes more ambitious
