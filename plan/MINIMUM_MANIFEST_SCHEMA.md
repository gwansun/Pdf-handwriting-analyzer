# PDF Handwriting Analyzer - Minimum Manifest Schema

## 1. Purpose

Define the minimum required structure for a template `manifest.json` in the MVP.

This is the smallest acceptable template manifest that still allows:
- template matching
- schema loading
- runtime extraction setup

---

## 2. MVP Principle

For MVP, `manifest.json` should be:
- small
- explicit
- easy to hand-review
- enough for matching and schema lookup

Do not overload it with future-only fields.

---

## 3. Required Top-Level Fields

Every template manifest must include:

```json
{
  "template_id": "string",
  "template_family": "string",
  "template_version": "string",
  "display_name": "string",
  "status": "draft | active | deprecated",
  "fingerprints": {},
  "schema_ref": {},
  "runtime_hints": {}
}
```

---

## 4. Required Identity Fields

### `template_id`
Stable identifier for one template version.

Example:
```json
"template_id": "t2200_fill_25e"
```

### `template_family`
Broader family name.

Example:
```json
"template_family": "t2200"
```

### `template_version`
Version string for the exact template variant.

Example:
```json
"template_version": "2025-en-v1"
```

### `display_name`
Human-readable label.

### `status`
Allowed MVP values:
- `draft`
- `active`
- `deprecated`

---

## 5. Required `fingerprints` Structure

For MVP, `fingerprints` must include:

```json
"fingerprints": {
  "page_signature": {
    "page_count": 3
  }
}
```

### Required inside `page_signature`
- `page_count`

### Strongly recommended MVP additions
- `page_sizes`
- `metadata`
- `acroform`
- `anchor_text`

### Recommendation
For forms like T2200, `acroform` should be treated as practically required even if technically optional in the minimum schema.

---

## 6. Required `schema_ref` Structure

`schema_ref` must include:

```json
"schema_ref": {
  "schema_path": "templates/t2200_fill_25e/schema.json",
  "blank_pdf_path": "templates/t2200_fill_25e/t2200-fill-25e.pdf"
}
```

### Required fields
- `schema_path`
- `blank_pdf_path`

These are needed so the analyzer can:
- load the canonical schema
- trace back to the blank template input

---

## 7. Required `runtime_hints` Structure

For MVP, `runtime_hints` must include:

```json
"runtime_hints": {
  "default_input_mode": "mixed",
  "primary_language": "en",
  "alignment_mode": "strict"
}
```

### Required fields
- `default_input_mode`
- `primary_language`
- `alignment_mode`

Allowed `alignment_mode` values for MVP:
- `strict`
- `normal`
- `relaxed`

---

## 8. Strongly Recommended Optional Fields

These are not mandatory for the minimum manifest, but are highly useful:

### In `fingerprints`
- `metadata.title`
- `metadata.creator`
- `acroform.field_count`
- `acroform.field_names`
- `anchor_text.phrases`
- `page_signature.page_sizes`

### In `schema_ref`
- `anchors_path`
- `assets.page_images_dir`

### In `runtime_hints`
- `preferred_extractors`
- `unknown_field_policy`

---

## 9. Minimum Valid Example

```json
{
  "template_id": "t2200_fill_25e",
  "template_family": "t2200",
  "template_version": "2025-en-v1",
  "display_name": "T2200 Declaration of Conditions of Employment",
  "status": "active",
  "fingerprints": {
    "page_signature": {
      "page_count": 3
    },
    "acroform": {
      "field_count": 181,
      "field_names": [
        "Last_Name_Fill",
        "First_Name_Fill",
        "Tax_Year_Fill",
        "Job_Title_Fill"
      ]
    }
  },
  "schema_ref": {
    "schema_path": "templates/t2200_fill_25e/schema.json",
    "blank_pdf_path": "templates/t2200_fill_25e/t2200-fill-25e.pdf"
  },
  "runtime_hints": {
    "default_input_mode": "mixed",
    "primary_language": "en",
    "alignment_mode": "strict"
  }
}
```

---

## 10. Validation Rules

A manifest should be rejected for MVP if:
- `template_id` is missing
- `status` is missing
- `fingerprints.page_signature.page_count` is missing
- `schema_ref.schema_path` is missing
- `schema_ref.blank_pdf_path` is missing
- `runtime_hints.default_input_mode` is missing
- `runtime_hints.primary_language` is missing
- `runtime_hints.alignment_mode` is missing

---

## 11. Final Recommendation

For MVP, keep `manifest.json` small but strict.

It should contain just enough to:
- identify a template
- connect matching signals
- resolve the schema
- provide runtime defaults

Everything else can grow later.
