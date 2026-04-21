# PDF Handwriting Analyzer - Minimum Schema Field Format

## 1. Purpose

Define the minimum required field structure inside `schema.json` for the analyzer MVP.

This is the smallest field definition format that still supports:
- matched-template runtime flow
- field routing
- extraction
- validation
- confidence scoring

---

## 2. MVP Principle

For MVP, each field definition should contain only the information required to:
- locate the field
- understand its meaning
- route it to the right extractor
- apply basic validation hints

Do not overload the schema with too many future-only attributes.

---

## 3. Minimum Top-Level Schema Shape

```json
{
  "template_id": "string",
  "pages": [],
  "fields": []
}
```

### Required top-level fields
- `template_id`
- `pages`
- `fields`

---

## 4. Required Page Object

Each page object must include:

```json
{
  "page_number": 1,
  "width": 2550,
  "height": 3300,
  "unit": "px"
}
```

### Required fields
- `page_number`
- `width`
- `height`
- `unit`

---

## 5. Required Field Object

Each field entry in `fields[]` must include:

```json
{
  "field_id": "string",
  "field_name": "string",
  "field_label": "string",
  "page_number": 1,
  "bbox": [0, 0, 0, 0],
  "field_type": "string",
  "input_mode": "string",
  "required": false,
  "runtime_hints": {},
  "validation_rules": []
}
```

---

## 6. Required Field Attributes

### `field_id`
Stable internal identifier.

### `field_name`
Machine-usable field name returned in analyzer output.

### `field_label`
Human-readable label.

### `page_number`
Which template page contains the field.

### `bbox`
Field bounding box in template coordinate system.

Format:
```json
[x1, y1, x2, y2]
```

### `field_type`
Required MVP values may include:
- `text`
- `number`
- `date`
- `checkbox`
- `radio`
- `signature`
- `unknown`

### `input_mode`
Required MVP values may include:
- `typed`
- `handwritten`
- `mixed`
- `selection`
- `signature`
- `unknown`

### `required`
Boolean indicating whether field is expected to be populated.

### `runtime_hints`
Per-field runtime guidance.

### `validation_rules`
List of basic validation hints.

---

## 7. Required `runtime_hints` Minimum

For MVP, `runtime_hints` should support at least:

```json
{
  "preferred_extractor": "native_text_first",
  "language_hint": "en"
}
```

### Required MVP fields inside `runtime_hints`
- `preferred_extractor`
- `language_hint`

This helps field routing remain explicit.

---

## 8. Validation Rule Format

For MVP, `validation_rules` can be a simple array of strings.

Example:
```json
[
  "non_empty_if_form_submitted",
  "year_format"
]
```

This can later evolve into structured rule objects if needed.

---

## 9. Strongly Recommended Optional Field Attributes

These are not mandatory for MVP but are useful:
- `context_bbox`
- `section_id`
- `expected_format`
- `allowed_values`
- `max_length`
- `reading_order_index`

### Recommendation
For handwritten-heavy forms, `context_bbox` is especially useful and may become practically important early.

---

## 10. Minimum Valid Field Example

```json
{
  "field_id": "employee_first_name",
  "field_name": "employee_first_name",
  "field_label": "First name",
  "page_number": 1,
  "bbox": [540, 320, 880, 395],
  "field_type": "text",
  "input_mode": "handwritten",
  "required": true,
  "runtime_hints": {
    "preferred_extractor": "handwriting_ocr",
    "language_hint": "en"
  },
  "validation_rules": [
    "non_empty_if_form_submitted"
  ]
}
```

---

## 11. T2200 Example Snippet

```json
{
  "template_id": "t2200_fill_25e",
  "pages": [
    {
      "page_number": 1,
      "width": 2550,
      "height": 3300,
      "unit": "px"
    }
  ],
  "fields": [
    {
      "field_id": "employee_last_name",
      "field_name": "employee_last_name",
      "field_label": "Last name",
      "page_number": 1,
      "bbox": [210, 320, 520, 395],
      "field_type": "text",
      "input_mode": "handwritten",
      "required": true,
      "runtime_hints": {
        "preferred_extractor": "handwriting_ocr",
        "language_hint": "en"
      },
      "validation_rules": [
        "non_empty_if_form_submitted"
      ]
    },
    {
      "field_id": "tax_year",
      "field_name": "tax_year",
      "field_label": "Tax year",
      "page_number": 1,
      "bbox": [900, 320, 1010, 395],
      "field_type": "number",
      "input_mode": "typed",
      "required": true,
      "runtime_hints": {
        "preferred_extractor": "native_text_first",
        "language_hint": "en"
      },
      "validation_rules": [
        "year_format"
      ]
    }
  ]
}
```

---

## 12. Validation Rules For Schema Acceptance

A field definition should be rejected for MVP if any of these are missing:
- `field_id`
- `field_name`
- `field_label`
- `page_number`
- `bbox`
- `field_type`
- `input_mode`
- `required`
- `runtime_hints.preferred_extractor`
- `runtime_hints.language_hint`
- `validation_rules`

---

## 13. Final Recommendation

For MVP, keep each field definition simple but strict.

Each field should answer these questions clearly:
- where is it?
- what does it mean?
- what kind of content is expected?
- which extractor should be tried first?
- what basic validation should apply?

That is enough to drive matched-template extraction reliably.
