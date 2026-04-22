# PDF Handwriting Analyzer - Unknown Template Policy

## 1. Purpose

Define what the analyzer should do when an incoming PDF does not clearly match a known template.

This policy matters because bad template assumptions can produce confidently wrong field extraction.

---

## 2. Core Principle

When template certainty is low, the analyzer should be conservative.

It is better to return:
- `review_required`,
- low-confidence partial output,
- or structured failure for unsupported file types

than to perform unreliable extraction and pretend the output is trustworthy.

---

## 3. Policy Split

Unknown-input handling should be split by **document type**, not treated as one single bucket.

### Policy 1. Known matched template
If the incoming PDF matches a registered template:
- use the normal matched-template extraction flow
- keep existing behavior

### Policy 2. Blank/canonical PDF with no template artifacts yet
If the incoming file is a valid PDF and is judged to be a blank or canonical template candidate, but no template manifest/schema exists yet:
- do **not** fail fast
- run the template registration workflow
- generate template artifacts
- save them into the template folder
- make them available for future matching/runtime use

### Policy 3. Filled PDF with no registered template yet
If the incoming file is a valid filled PDF but does not match any registered template:
- do **not** fail fast
- attempt provisional extraction using a generic fallback path
- return `review_required`
- keep confidence conservative
- clearly mark template status as unknown/unmatched

### Policy 4. Unsupported / invalid non-PDF input
If the incoming file is not actually a PDF or is otherwise unsupported:
- fail fast
- return structured failure

---

## 4. Recommended Default Behavior

### 4.1 Blank PDF + manifest/schema already prepared
Keep current behavior:
- load template from registry
- use matched-template runtime flow

### 4.2 Blank PDF exists only as raw file, no template artifacts
Expected behavior:
- inspect blank PDF
- generate:
  - `manifest.json`
  - `schema.json`
  - optional `anchors.json`
  - optional rendered page assets
- save artifacts under `templates/<template_id>/`
- register template for future use

### 4.3 Filled PDF arrives before template registration
Expected behavior:
- attempt provisional extraction
- return top-level `status = review_required`
- set summary fields conservatively:
  - `template_match_status = "unknown"` or `"unmatched"`
  - `template_id = null`
  - low `overall_confidence`
  - `review_required = true`
- include warnings explaining that no registered template was found
- allow zero fields or partial fields depending on fallback extraction quality

### 4.4 Unknown file, not actually a PDF
Expected behavior:
- top-level `status = failed`
- structured error such as `NOT_A_PDF` or `UNREADABLE_FILE`
- no fallback extraction

---

## 5. Blank PDF Auto-Registration Policy

If a clean blank/canonical PDF is available but its template folder is incomplete:
- the system should treat it as a **template registration opportunity**
- not as a normal extraction failure

### Registration outputs
The workflow should generate and persist:
- `manifest.json`
- `schema.json`
- optional `anchors.json`
- stored blank PDF in template folder
- optional page render assets / overlays

### Registration result expectations
- newly generated templates should normally start as `draft`
- they may become `active` after light review
- once registered, future filled PDFs can use normal matched-template extraction

### Important guardrail
Do **not** auto-register arbitrary unknown PDFs as templates unless the system is sufficiently confident they are blank/canonical forms.
Heavily filled documents should not silently become template sources.

---

## 6. Unknown Filled-PDF Fallback Policy

When a valid PDF appears to be a filled document but does not match any known template, the analyzer should use a provisional fallback path.

### Fallback goals
- provide best-effort extraction when possible
- avoid total failure for potentially useful documents
- keep uncertainty explicit

### Fallback constraints
- output must be marked `review_required`
- confidence should remain conservative
- output should not pretend template certainty exists
- downstream systems should understand these fields are provisional

### Suggested summary behavior
```json
{
  "template_match_status": "unknown",
  "template_id": null,
  "overall_confidence": 0.35,
  "review_required": true,
  "field_count": 0
}
```

### Suggested warning behavior
```json
[
  {
    "code": "UNKNOWN_TEMPLATE",
    "message": "No matching registered template was found. Provisional extraction was used."
  }
]
```

### Suggested top-level status
Use:
- `status = review_required`

Do not use top-level `failed` unless:
- the PDF is invalid,
- the file cannot be read,
- or the fallback extraction itself crashes.

---

## 7. Email Manager Integration Impact

Email Manager should interpret analyzer output as follows:

### Known template path
- normal completed/review flow

### Blank-PDF registration path
- template artifacts were generated or updated
- future documents of this template family may match normally
- this is a registration event, not a normal field-extraction result

### Unknown filled-PDF fallback path
- analysis completed provisionally
- result must be treated as review-required
- no strong trust should be placed on extracted fields until reviewed

### Invalid non-PDF path
- analysis failed safely
- no retry via extraction logic unless the input file is corrected

---

## 8. Recommendation

Adopt the following concrete rules:
- known template -> analyze normally
- blank PDF with existing manifest/schema -> keep as is
- blank PDF with no template artifacts -> auto-generate template artifacts and register
- filled PDF with no registered template -> provisional extraction with `review_required`
- non-PDF / invalid file -> fail fast

This gives the system a better long-term product behavior than strict fail-fast-only unknown-template handling, while still keeping uncertainty explicit and safe.
