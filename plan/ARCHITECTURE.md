# PDF Handwriting Analyzer - Full System Architecture Diagram (Text Skeleton)

## 1. Goal

Build a system that analyzes PDF forms containing a mix of:
- printed/electronic text
- handwritten text
- lines, boxes, and section boundaries
- structured input fields

The system should:
- use a template-first approach
- extract field-level values from filled PDFs
- assign confidence scores in the range `0.0 - 1.0`
- produce a structured output report for downstream review or automation

---

## 2. High-Level Architecture

```text
[Empty Template PDF]
        |
        v
[Template Analysis Layer]
        |
        v
[Template Schema / Field Map]
        |
        +------------------------------+
        |                              |
        v                              |
[Filled PDF Input]                     |
        |                              |
        v                              |
[Preprocessing + Alignment Layer]      |
        |                              |
        v                              |
[Field Region Extraction Layer] <------+
        |
        v
[Field Type Classification Layer]
        |
        +-------------------------------+-------------------------------+
        |                               |                               |
        v                               v                               v
[Typed Text OCR]               [Handwriting Extraction]        [Checkbox / Signature / Other]
        |                               |                               |
        +-------------------------------+-------------------------------+
                                        |
                                        v
                         [Confidence Scoring + Validation Layer]
                                        |
                                        v
                              [Structured Report Generator]
                                        |
                                        v
                             [JSON / CSV / Review UI Output]
```

---

## 3. Main System Layers

### 3.1 Template Analysis Layer
Purpose:
- analyze the empty template PDF
- detect layout structure
- identify sections, columns, lines, boxes, and field boundaries
- associate labels with candidate input fields

Inputs:
- empty PDF template

Outputs:
- normalized template schema
- field bounding boxes
- section hierarchy
- anchor text and structural metadata

---

### 3.2 Template Schema / Field Map
Purpose:
- store canonical representation of the form
- serve as the reference for later field extraction

Possible contents:
- page number
- field id
- field name
- field type
- bounding box coordinates
- anchor labels
- section/group name
- expected input mode (typed / handwritten / mixed / checkbox / signature)
- validation hints

---

### 3.3 Preprocessing + Alignment Layer
Purpose:
- normalize incoming filled PDFs
- align each page against the template
- correct skew, rotation, scale, and translation shifts

Key tasks:
- render PDF page to image when needed
- denoise
- deskew
- page registration using anchors or layout lines
- template-to-instance coordinate transformation

---

### 3.4 Field Region Extraction Layer
Purpose:
- crop each expected field region from the aligned filled document
- preserve field-level image snippets for extraction and audit

Outputs:
- per-field cropped image region
- per-field page coordinates
- extraction context metadata

---

### 3.5 Field Type Classification Layer
Purpose:
- determine how each field should be processed

Candidate classes:
- empty
- typed text
- handwritten text
- mixed typed + handwritten
- checkbox / radio
- signature
- stamp / seal
- unknown

Outputs:
- field processing route
- field content type confidence

---

### 3.6 Extraction Layer
Purpose:
- run the correct extractor for each field type

Sub-components:
- typed OCR engine
- handwriting OCR / multimodal extraction engine
- checkbox detector
- signature presence detector
- fallback multimodal analyzer

Outputs:
- extracted value
- model-native confidence
- optional alternate candidates

---

### 3.7 Confidence Scoring + Validation Layer
Purpose:
- combine multiple evidence signals into a final field confidence score
- validate extracted outputs against known patterns or business rules

Confidence signal examples:
- OCR token confidence
- handwriting model confidence
- image quality score
- alignment quality
- pattern validation score
- semantic consistency with nearby fields
- agreement between multiple extractors
- field occupancy / partial clipping detection

Outputs:
- final confidence in `0.0 - 1.0`
- validation warnings
- review-required flag

---

### 3.8 Structured Report Generator
Purpose:
- generate machine-readable and human-review outputs

Output formats:
- JSON
- CSV
- annotated PDF
- review dashboard payload

Field-level output example:
- field name
- extracted value
- confidence score
- extraction type
- page number
- bounding box
- validation notes
- evidence metadata

---

## 4. Core Data Flow

```text
Template PDF
  -> Template parser
  -> Layout detection
  -> Field schema generation
  -> Stored template definition

Filled PDF
  -> Page preprocessing
  -> Template alignment
  -> Field cropping
  -> Field type routing
  -> OCR / handwriting extraction
  -> Validation + confidence fusion
  -> Final structured report
```

---

## 5. Major Components

### Component A. Template Parser
- PDF structure reader
- page geometry reader
- label and line detector

### Component B. Layout Analyzer
- section segmentation
- line / table / box detection
- field candidate generator

### Component C. Template Schema Builder
- converts raw layout findings into canonical field definitions

### Component D. Document Registration Engine
- aligns filled pages to template coordinates

### Component E. Field Cropper
- crops per-field regions after alignment

### Component F. Field Router
- chooses extraction path based on field type

### Component G. OCR / Handwriting Engines
- typed OCR
- handwriting extraction
- multimodal fallback

### Component H. Confidence Engine
- aggregates evidence
- calibrates confidence score
- marks low-confidence items for review

### Component I. Report Builder
- exports structured outputs
- optional visual audit artifacts

---

## 6. Suggested Logical Modules

```text
/pdf-handwriting-analyze
  /plan
    ARCHITECTURE.md
  /src
    /template
    /alignment
    /segmentation
    /classification
    /extractors
    /confidence
    /reporting
    /common
  /tests
  /samples
    /templates
    /filled
  /schemas
  /docs
```

---

## 7. Open Design Questions

- How will template fields be labeled: automatic, manual, or hybrid?
- Should template schema be editable by humans?
- Which extraction engine should be primary for handwriting?
- Should confidence be calibrated statistically on labeled data?
- Will multi-page forms share repeated section definitions?
- How should ambiguous overlapping fields be resolved?
- What is the review workflow for low-confidence fields?

---

## 8. Recommended Next Planning Docs

Possible next documents:
- `plan/PIPELINE.md`
- `plan/TEMPLATE_SCHEMA.md`
- `plan/CONFIDENCE_SCORING.md`
- `plan/MODEL_STACK.md`
- `plan/MVP_SCOPE.md`
- `plan/API_DESIGN.md`

---

## 9. MVP Direction

Recommended MVP:
- support one template family
- support one filled PDF at a time
- support typed + handwritten text fields
- output field-level JSON
- include confidence score and review flag
- skip advanced UI initially

---

## 10. Summary

This system should be designed as a hybrid pipeline:
- deterministic layout grounding from template structure
- alignment of filled forms to template coordinates
- field-by-field extraction using specialized engines
- confidence scoring from multiple evidence sources
- structured reporting for downstream review and automation
