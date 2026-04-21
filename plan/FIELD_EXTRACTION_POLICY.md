# PDF Handwriting Analyzer - Field Extraction Policy

## 1. Purpose

Define how the analyzer decides which extraction method to use for each field in a matched-template document.

This policy sits between:
- matched-template field mapping,
- and final field extraction.

Its job is to route each field to the most reliable extraction path.

---

## 2. Goal

For every field in a matched template, decide whether to use:
- native PDF extraction
- typed OCR
- handwriting OCR
- checkbox/radio detection
- signature detection
- multimodal fallback

The selection should be conservative and explainable.

---

## 3. Core Principle

Use the simplest reliable extraction path first.

Recommended priority:
1. direct/native extraction when trustworthy
2. specialized extractor for known field class
3. OCR for image-based text fields
4. multimodal fallback only when needed

This reduces unnecessary model complexity and keeps behavior predictable.

---

## 4. Inputs to Routing Decision

Field routing should use multiple inputs:

### Schema-derived inputs
- `field_type`
- `input_mode`
- `expected_format`
- `preferred_extractor`
- `fallback_extractor`
- field bbox / context bbox

### Runtime-derived inputs
- document class: native / scanned / hybrid
- native text present in bbox or not
- crop appearance
- alignment quality
- field occupancy
- checkbox/signature visual cues

---

## 5. Extraction Routes

## Route A. Native PDF extraction
Use when:
- document contains real text/form content in the field region
- field is typed or fillable
- extracted text is structurally plausible

Best for:
- AcroForm text fields
- born-digital typed forms
- machine-generated values

Advantages:
- fast
- deterministic
- usually cleaner than OCR

Risks:
- hidden OCR text layers may be misleading in hybrid PDFs
- stale or misaligned text objects can produce wrong values

---

## Route B. Typed OCR
Use when:
- field appears image-based
- content is typed/printed rather than handwritten
- native text is absent or unreliable

Best for:
- scanned typed forms
- rasterized typed entries

---

## Route C. Handwriting OCR
Use when:
- schema says `handwritten` or `mixed`
- crop appears handwritten
- field is likely free-form handwritten text

Best for:
- names
- notes
- manually filled dates
- handwritten identifiers
- text entered on printed forms by hand

### Required output behavior
For handwritten fields, the analyzer should preserve the original form field meaning and return:
- interpreted text value
- confidence score for the interpreted value

Example:
```json
{
  "field_name": "employee_name",
  "field_label": "Employee name",
  "field_type": "handwritten_name",
  "value": "Leonardo Romero",
  "confidence": 0.90
}
```

The goal is not to flatten the form into generic OCR text.
The goal is to keep the same field structure while attaching interpreted handwritten values and confidence.

---

## Route D. Checkbox / radio detector
Use when:
- `field_type` is `checkbox` or `radio`
- schema geometry defines selection controls

Best for:
- yes/no answers
- check marks
- circular radio groups

---

## Route E. Signature detector
Use when:
- `field_type` is `signature`

Best for:
- presence/absence of signature
- optionally rough signature region occupancy

Note:
- this route detects presence, not identity verification

---

## Route F. Multimodal fallback
Use when:
- routing is uncertain
- OCR result is weak or suspicious
- schema and visual cues disagree
- field is hard free-form content

Best for:
- difficult mixed-content fields
- ambiguous handwritten text
- stubborn edge cases

Important:
- fallback should be used selectively, not as the default path

---

## 6. Routing Rules by Field Type

## 6.1 Text fields
### If schema/input suggests typed
- try native extraction first if trustworthy
- otherwise typed OCR

### If schema/input suggests handwritten
- use handwriting OCR
- fall back to multimodal review if needed

### If schema says mixed
- check for native text first
- if absent or weak, use handwriting OCR or OCR depending on crop appearance

---

## 6.2 Number fields
- prefer native extraction if available
- otherwise OCR/handwriting path based on appearance
- validate aggressively after extraction

---

## 6.3 Date fields
- prefer native extraction if available
- otherwise OCR/handwriting route based on actual content style
- apply strict date normalization and validation

---

## 6.4 Checkbox / radio fields
- always prefer specialized detector
- do not treat them as normal text fields

---

## 6.5 Signature fields
- use signature detector when the field meaning is presence/absence of signature
- use handwriting text interpretation when the business meaning of the field is the signed handwritten name or handwritten content itself

Important distinction:
- `signature_presence` means detect whether a signature exists
- `handwritten_name` or equivalent means interpret handwritten text and return the text value with confidence

---

## 7. Native Extraction Trust Policy

Native extraction should not be used blindly.

Treat native extraction as trustworthy when:
- the PDF is born-digital or fillable
- native text intersects the field bbox cleanly
- field content matches expected field type/format
- alignment is good

Treat native extraction as suspicious when:
- document is hybrid with questionable hidden text layer
- text appears outside expected region
- text is inconsistent with validation rules
- alignment is weak

In suspicious cases:
- reduce trust
- try alternate extraction path
- or send to multimodal fallback

---

## 8. Hybrid PDF Policy

Hybrid PDFs are tricky because they may contain:
- a page image
- hidden OCR text
- fillable form layers

Recommended behavior:
- prefer native extraction only if evidence is strong
- otherwise compare native result against OCR or validation
- if disagreement is meaningful, mark review or use fallback

---

## 9. Routing Output Structure

Each field router decision should produce something like:

```json
{
  "field_name": "tax_year",
  "selected_route": "native_pdf",
  "route_confidence": 0.91,
  "reasons": [
    "acroform_text_present",
    "field_type_text",
    "alignment_good"
  ]
}
```

This is helpful for debugging and confidence explainability.

---

## 10. T2200 Example Guidance

For the T2200 example pair:
- AcroForm fields exist and are strong structure signals
- some fields may be readable directly from form/native content
- handwritten fields should preserve the same field meaning while returning interpreted text and confidence
- signed/filled fields may still require visual confirmation or alternate extraction depending on how the PDF stores final values

Recommended initial policy for T2200-like fillable forms:
1. inspect whether field has usable AcroForm/native value
2. if yes, prefer native extraction
3. if no, inspect crop appearance
4. for handwritten fields, return interpreted handwritten text plus confidence
5. use typed OCR for rasterized typed fields
6. use checkbox/signature detectors only for true control/presence fields

---

## 11. MVP Recommendation

For MVP, support these routing policies:
- native-first for trustworthy fillable/native text fields
- OCR for rasterized typed fields
- handwriting OCR for handwritten/mixed text fields
- specialized detection for checkbox/radio/signature
- fallback only for uncertain cases

Keep the first version rule-based and explainable.

---

## 12. Final Recommendation

The field extraction policy should be conservative, field-aware, and template-aware.

The key idea is:
- do not run one extractor on everything
- use the template schema and runtime cues to choose the most reliable path per field
- preserve the original form structure and field meaning
- for handwritten fields, return interpreted text values with attached confidence rather than only generic OCR output
