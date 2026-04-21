# PDF Handwriting Analyzer - Template Schema Plan

## 1. Purpose

Define the canonical schema for representing an empty PDF form template.

The schema should capture:
- page structure
- section hierarchy
- field locations
- labels and anchors
- expected field types
- validation hints
- extraction guidance for runtime processing

---

## 2. Design Goals

The template schema should be:
- deterministic
- machine-readable
- human-reviewable
- versionable
- editable when automatic detection is imperfect
- stable enough for runtime field extraction

---

## 3. Top-Level Schema Structure

```json
{
  "template_id": "string",
  "template_name": "string",
  "template_version": "string",
  "source_file": "string",
  "pages": [],
  "sections": [],
  "fields": [],
  "metadata": {}
}
```

---

## 4. Core Entities

### 4.1 Template
Represents the complete form definition.

Suggested fields:
- `template_id`
- `template_name`
- `template_version`
- `source_file`
- `page_count`
- `created_at`
- `updated_at`
- `coordinate_system`
- `metadata`

---

### 4.2 Page
Represents a page in the template.

Suggested fields:
- `page_number`
- `width`
- `height`
- `unit`
- `rotation`
- `anchors`
- `layout_elements`

---

### 4.3 Section
Represents a logical group of fields.

Suggested fields:
- `section_id`
- `section_name`
- `page_number`
- `bbox`
- `parent_section_id`
- `label_text`
- `layout_type`

Examples:
- patient information
- billing information
- contact details
- signatures

---

### 4.4 Field
Represents one input region.

Suggested fields:
- `field_id`
- `field_name`
- `field_label`
- `page_number`
- `section_id`
- `bbox`
- `context_bbox`
- `field_type`
- `input_mode`
- `expected_format`
- `required`
- `anchors`
- `validation_rules`
- `runtime_hints`

---

### 4.5 Anchor
Represents text or geometry used for alignment or identification.

Suggested fields:
- `anchor_id`
- `anchor_type`
- `text`
- `bbox`
- `page_number`
- `confidence`

Possible anchor types:
- printed_label
- horizontal_line
- vertical_line
- box_corner
- table_boundary
- heading_text

---

## 5. Recommended Field Attributes

### 5.1 Field identity
- `field_id`: stable internal id
- `field_name`: normalized machine name
- `field_label`: nearby human-readable label

### 5.2 Geometry
- `bbox`: exact input region
- `context_bbox`: larger nearby region for contextual extraction
- `page_number`
- `reading_order_index`

### 5.3 Content expectation
- `field_type`
- `input_mode`
- `expected_format`
- `allowed_values`
- `max_length`

### 5.4 Processing hints
- `preferred_extractor`
- `fallback_extractor`
- `language_hint`
- `handwriting_expected`
- `multiline`

### 5.5 Validation hints
- `required`
- `validation_rules`
- `cross_field_dependencies`

---

## 6. Suggested Enumerations

### 6.1 `field_type`
- `text`
- `number`
- `date`
- `checkbox`
- `radio`
- `signature`
- `stamp`
- `table_cell`
- `unknown`

### 6.2 `input_mode`
- `typed`
- `handwritten`
- `mixed`
- `selection`
- `signature`
- `unknown`

### 6.3 `layout_type`
- `single_field`
- `row_group`
- `column_group`
- `table`
- `freeform`

---

## 7. Example Template Schema

```json
{
  "template_id": "medical_form_v1",
  "template_name": "Medical Intake Form",
  "template_version": "1.0.0",
  "source_file": "templates/medical_form_blank.pdf",
  "pages": [
    {
      "page_number": 1,
      "width": 2550,
      "height": 3300,
      "unit": "px"
    }
  ],
  "sections": [
    {
      "section_id": "patient_info",
      "section_name": "Patient Information",
      "page_number": 1,
      "bbox": [100, 200, 2200, 900],
      "parent_section_id": null,
      "label_text": "Patient Information",
      "layout_type": "column_group"
    }
  ],
  "fields": [
    {
      "field_id": "patient_name",
      "field_name": "patient_name",
      "field_label": "Patient Name",
      "page_number": 1,
      "section_id": "patient_info",
      "bbox": [250, 320, 1200, 430],
      "context_bbox": [150, 280, 1350, 470],
      "field_type": "text",
      "input_mode": "mixed",
      "expected_format": "person_name",
      "required": true,
      "anchors": ["anchor_patient_name_label"],
      "validation_rules": ["non_empty_if_form_submitted"],
      "runtime_hints": {
        "preferred_extractor": "handwriting_or_typed_router",
        "language_hint": "en"
      }
    }
  ],
  "metadata": {
    "notes": "Initial manually reviewed schema"
  }
}
```

---

## 8. Coordinate System Strategy

Choose one canonical coordinate system.

Recommended options:
- PDF-native coordinates
- rendered image pixel coordinates at fixed DPI

Recommendation for MVP:
- use rendered image pixel coordinates at a fixed DPI for easier alignment and cropping

But preserve mapping to original PDF coordinates if possible.

---

## 9. Human-in-the-Loop Editing

The schema should allow manual correction after auto-detection.

Editable items:
- field names
- bounding boxes
- section groupings
- expected field types
- validation hints
- extractor preferences

---

## 10. Versioning Strategy

The template schema should be versioned.

Reasons:
- templates may evolve
- field coordinates may be refined
- extraction hints may improve over time

Suggested version rules:
- patch: metadata or hint fixes
- minor: field definition improvements
- major: layout-breaking changes

---

## 11. Runtime Usage

At runtime, the schema should support:
- template matching
- page alignment
- field cropping
- field routing
- validation
- reporting with field provenance

---

## 12. Open Questions

- How much of field naming should be automated?
- Should section hierarchy be strict or optional?
- Should repeated tables use dynamic field groups?
- Should schema support multilingual labels?
- How should ambiguous unlabeled boxes be represented?

---

## 13. MVP Recommendation

For MVP, support only:
- fixed pages
- fixed fields
- rectangular bounding boxes
- one primary language
- simple validation hints
- optional manual schema correction
