# PDF Handwriting Analyzer - Internal Task Breakdown

## 1. Goal

Turn the analyzer planning docs into a more implementation-ready breakdown of modules and tasks.

---

## 2. Core Build Order

### Phase 1. Request/response boundary
Build:
- request validator
- response builder
- contract-compliant success/failure responses

### Phase 2. PDF intake and template match
Build:
- PDF inspector
- template registry loader
- template matcher

### Phase 3. Template-based extraction
Build:
- page alignment engine
- field cropper
- field router
- first extractor paths

### Phase 4. Validation and confidence
Build:
- normalizer/validator
- confidence engine
- review flag policy

### Phase 5. Hardening
Build:
- better warnings
- failure codes
- optional alternate candidates
- optional page summaries

---

## 3. Module-by-Module Tasks

## Module A. Request validator
Tasks:
- parse incoming JSON
- validate required keys
- verify file exists
- verify file is readable
- reject non-PDF inputs
- normalize request into internal runtime object

Definition of done:
- returns normalized request or structured failure

---

## Module B. PDF inspector
Tasks:
- open PDF
- count pages
- inspect metadata
- detect born-digital vs scanned vs hybrid
- expose per-page basic properties

Definition of done:
- returns reusable PDF inspection summary

---

## Module C. Template registry
Tasks:
- load registered template metadata
- load schema by template id
- expose fingerprints and anchors

Definition of done:
- analyzer can retrieve template definitions reliably

---

## Module D. Template matcher
Tasks:
- compute request-side fingerprint
- compare against registry
- rank candidate templates
- return matched/unknown status

Definition of done:
- analyzer can select known template or fail safely

---

## Module E. Alignment engine
Tasks:
- render pages to images when needed
- run deskew/normalize steps
- detect anchors
- estimate transform matrix
- score alignment quality

Definition of done:
- field coordinates can be mapped onto aligned document pages

---

## Module F. Field cropper
Tasks:
- load field bounding boxes from template
- apply alignment transform
- crop field and context images
- keep page/bbox metadata

Definition of done:
- each field has extraction-ready crop data

---

## Module G. Field router
Tasks:
- classify field content class
- decide native extraction vs OCR vs checkbox/signature path
- emit routing confidence

Definition of done:
- every field gets an extraction route or explicit fallback

---

## Module H. Extractors

### H1. Native text extractor
Tasks:
- extract native PDF text in bbox
- return text and confidence proxy

### H2. Typed OCR extractor
Tasks:
- OCR typed field crops
- return text and confidence

### H3. Handwriting extractor
Tasks:
- run handwriting-capable OCR/VLM path
- return text and candidates

### H4. Checkbox extractor
Tasks:
- detect selected/unselected state

### H5. Signature extractor
Tasks:
- detect presence/absence

Definition of done:
- first-pass extractors work on matched-template fields

---

## Module I. Validator / normalizer
Tasks:
- normalize dates, numbers, text cleanup
- validate field-specific rules
- attach warnings and validation status

Definition of done:
- extracted values are normalized and checked consistently

---

## Module J. Confidence engine
Tasks:
- combine extractor/image/alignment/validation signals
- assign field confidence
- assign document-level review flag
- emit optional breakdown

Definition of done:
- response includes consistent field confidence and review flags

---

## Module K. Response builder
Tasks:
- map internal results to public contract
- include summary, fields, warnings
- emit structured failure object when needed

Definition of done:
- Email Manager can consume analyzer responses without knowing internals

---

## 4. MVP Success Criteria

The analyzer MVP is ready when:
- it accepts the agreed request contract
- it reads PDF from local `file.path`
- it matches known templates reliably enough for test forms
- it extracts field-level values for matched templates
- it returns confidence and review flags
- it fails safely for unknown templates
- it returns contract-compliant JSON to Email Manager

---

## 5. Recommended Immediate Next Step

If implementation starts, begin with:
1. request validator
2. PDF inspector
3. template registry + matcher
4. response builder

That gives a thin but real vertical slice early.
