# Implementation Plan - Gemma Whole-PDF Review Pass

## Goal

Replace the current **per-field Gemma review** workflow with a **single Gemma review pass per PDF**.

GLM-OCR remains the primary extractor for handwritten fields and can continue to run per field.
Gemma should no longer be called once per low-confidence field.
Instead:

- run first-pass extraction for all fields
- mark field-level `review_required` during extraction/fallback logic
- if **any field** is `review_required`, call Gemma **once** for the entire PDF
- provide Gemma with the best available document context
- support both:
  - matched-template review with manifest/schema metadata
  - fallback review when manifest/schema metadata does not exist
- merge the reviewed results back into the document response

This reduces repeated Gemma calls and gives the review model full-form context.

---

## Why this change

## Current problem

Current behavior before this change:
- GLM-OCR is called per handwritten field
- if a field confidence is `< 0.70`, Gemma is called **per field**
- a PDF with many weak handwritten fields can trigger many Gemma requests

Problems:
- expensive and slow
- Gemma lacks whole-document context
- neighboring field semantics are invisible to Gemma
- repeated small calls are a poor fit for a review/refine model
- review is overly dependent on matched manifest/schema context

## Desired behavior

Gemma should act as a **document-level review layer**, not a field-level OCR loop.
It should still be usable when template metadata is missing.

---

## New high-level workflow

```text
validate request
  -> inspect PDF
  -> try template match
  -> if matched: load manifest + schema
  -> extract all fields / provisional outputs
  -> mark field-level review_required flags
  -> if no fields need review:
       return normal response
  -> if any field needs review:
       build one Gemma review payload for the entire PDF
       use matched-template payload if metadata exists
       otherwise use fallback review payload
       call Gemma once
       merge Gemma-reviewed outputs
       recompute document summary
       return review_required response
```

---

## Locked design decisions

### 1. GLM-OCR stays per field
This plan does **not** change primary extraction routing.
Only Gemma review changes.

### 2. Gemma review triggers once per PDF
Trigger rule:
- if **any field** is marked `review_required`
- and Gemma is available
- call Gemma **once** for the whole PDF

### 3. Gemma review must not depend on manifest/schema availability
Gemma should support two payload modes:

#### Mode A. Matched-template review
Used when template metadata exists.

#### Mode B. Fallback review without manifest/schema
Used when template metadata does not exist or schema cannot be loaded.

### 4. Gemma returns structured JSON
Avoid free-form `TEXT:/CONFIDENCE:/REASONING:` parsing.
Use JSON with one reviewed_fields collection.

### 5. Preserve original first-pass extraction
Do not lose the primary extraction.
The system should preserve the GLM or provisional first-pass value and confidence, even if Gemma supplies a reviewed value.

---

## Proposed data flow

## Phase 1. First-pass extraction

Run the current extraction/provisional pipeline.

Per field or provisional result, retain:
- `field_name`
- `field_label`
- `field_type`
- `page_number`
- `bbox`
- first-pass `value`
- first-pass `confidence`
- `review_required`
- `warnings`

No Gemma call happens inside field routing.

---

## Phase 2. Compute review trigger inputs

Build:
- field-level `review_required`
- `review_target_fields`
- document confidence summary for Gemma context

Recommended review target list:
- fields already marked `review_required`
- fields below the normal confidence threshold
- fields with warning-heavy outputs when useful
- provisional fields when schema is missing

If no fields are marked `review_required`:
- continue normal response path

If any field is marked `review_required`:
- invoke one document-level Gemma review pass

---

## Phase 3. Build document-level Gemma payload

## Mode A. Matched-template review payload

### Required PDF-level context
- `template_id`
- `template_family`
- `display_name`
- `template_version`
- `page_count`
- runtime hints:
  - `default_input_mode`
  - `primary_language`
  - `alignment_mode`
  - `unknown_field_policy`
  - `preferred_extractors`

### Required schema context
For every field in the schema:
- `field_name`
- `field_label`
- `field_type`
- `page_number`
- `bbox`
- options / enum values when present
- any semantic notes if later added

### Required first-pass extraction context
For every field result:
- `field_name`
- `value`
- `confidence`
- `review_required`
- `warnings`

### Required review trigger context
- document confidence summary
- explicit `review_target_fields`

---

## Mode B. Fallback review payload (no manifest/schema)

### Required fallback context
- request/job ids when helpful
- page count
- PDF metadata
- inspection signals
- AcroForm field names and values if available
- page text snippets if available
- provisional extraction results if available
- document confidence summary
- classification result if available
- warnings / error context

### Goal
Even without schema, Gemma should still receive enough information to:
- understand the document type approximately
- review weak provisional outputs
- provide structured review output conservatively

---

## Response merge rule

After Gemma review:
- preserve original first-pass `value`
- preserve original first-pass `confidence`
- attach Gemma-reviewed output separately in `review`
- do not overwrite first-pass `value` by default

This rule applies in both:
- matched-template review
- fallback/no-schema review

---

## Final document status rule

- if any field is `review_required` -> document status is `review_required`
- otherwise -> document follows normal completed flow

Gemma remains one-shot per PDF even though the trigger is field-driven.

---

## Notes
- This plan intentionally changes only Gemma orchestration, not the primary GLM extraction path.
- The threshold `0.70` still matters for extractor-level confidence heuristics where field-level `review_required` is set.
- The key architectural rule is now:
  - **field-driven trigger**
  - **document-level single Gemma call**
