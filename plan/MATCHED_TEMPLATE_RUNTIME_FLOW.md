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

This document does **not** define the unknown-template fallback path in full detail, but it does note that Gemma review should still be possible without manifest/schema metadata.

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
5. run first-pass extraction,
6. trigger one document-level Gemma review pass if needed,
7. validate and score results,
8. return structured JSON.

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
  -> run first-pass extraction
  -> compute first-pass field confidence
  -> compute average document confidence
  -> if average document confidence < 0.70:
       run one Gemma whole-document review pass
       merge reviewed outputs
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
The crop stage should not yet decide review behavior. It should prepare clean inputs first.

---

## Stage 6. Route field to extraction path

### Goal
Choose the best primary extraction strategy for each field.

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

## Stage 7. Run first-pass extraction

### Goal
Run the chosen extractor and gather primary extraction results.

### Outputs per field
- raw extracted value
- interpreted field value
- alternate candidates if available
- extractor confidence

### Important MVP rule
- GLM-OCR may still run per handwritten field
- Gemma does **not** run here per field
- this stage is first-pass extraction only

---

## Stage 8. Determine whether document-level review is needed

### Goal
Decide whether the PDF should enter the Gemma whole-document review pass.

### Rule
If **average document confidence** is `< 0.70`:
- trigger one Gemma review call for the whole PDF

### Inputs to Gemma review (matched-template path)
- template manifest/runtime hints
- full schema
- first-pass extraction results for all fields
- document confidence summary
- review target field list

### Inputs to Gemma review (fallback path when manifest/schema missing)
- PDF metadata
- page count
- inspection signals
- provisional extraction results if available
- AcroForm/page text signals if available
- document confidence summary
- classification / warning context

### Outputs from Gemma review
- reviewed field values for selected fields
- optional review notes / reasoning

### Merge behavior
- preserve original first-pass `value`
- preserve original first-pass `confidence`
- attach Gemma review output separately

---

## Stage 9. Validate and score results

### Goal
Run normalization, validation, and confidence aggregation.

### Actions
- validate individual field values
- compute document-level confidence summary
- determine `review_required`

### Rule
If average document confidence is `< 0.70`:
- top-level document status is `review_required`

---

## Stage 10. Build final response

### Goal
Return one structured JSON response that reflects:
- matched template result
- field extraction outputs
- review outputs when present
- document-level review state

### Response should contain
- top-level status
- summary
- fields
- warnings
- optional error section

---

## Notes
- This document reflects the whole-document Gemma review design.
- Gemma is a secondary review/refine layer, not the primary extractor.
- Gemma review should still be possible even when manifest/schema is unavailable.
- Detailed implementation plan: `IMPLEMENTATION_PLAN_GEMMA_WHOLE_PDF_REVIEW.md`
