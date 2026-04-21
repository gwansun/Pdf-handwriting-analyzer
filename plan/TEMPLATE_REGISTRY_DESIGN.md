# PDF Handwriting Analyzer - Template Registry Design

## 1. Purpose

Define how the analyzer stores and loads known PDF form templates for matching and runtime extraction.

The template registry is the source of truth for:
- what templates are known,
- how templates are identified,
- where their schemas live,
- and what runtime hints are available during extraction.

---

## 2. Role of the Template Registry

The template registry exists to support two main workflows:

### A. Template matching
Given an incoming PDF, the analyzer needs to compare it against known templates.

### B. Runtime extraction
Once a template is matched, the analyzer needs to load the correct schema, anchors, field definitions, and processing hints.

So the registry is not just a list of templates. It is the bridge between:
- template identification,
- and template-based extraction.

---

## 3. Registry Responsibilities

The registry should:
- store template identity metadata
- store template fingerprint signals used for matching
- point to the canonical template schema
- support versioning
- support multiple template revisions over time
- expose runtime hints needed after a match

The registry should **not** directly store all extracted field results from filled documents. That belongs to runtime result storage.

---

## 4. Core Registry Record

Each template registry record should represent one known template version.

Suggested top-level structure:

```json
{
  "template_id": "t2200_fill_25e",
  "template_family": "t2200",
  "template_version": "2025-en-v1",
  "display_name": "T2200 Declaration of Conditions of Employment",
  "status": "active",
  "fingerprints": {},
  "schema_ref": {},
  "runtime_hints": {},
  "created_at": "2026-04-20T17:00:00Z",
  "updated_at": "2026-04-20T17:00:00Z"
}
```

---

## 5. Required Registry Fields

### 5.1 Identity fields
- `template_id`: stable machine identifier for one exact template version
- `template_family`: broader form family, for example `t2200`
- `template_version`: version label for revisions
- `display_name`: human-readable name
- `status`: `active`, `deprecated`, `draft`

### 5.2 Matching fields
Stored under `fingerprints`:
- metadata fingerprint
- AcroForm fingerprint
- page signature
- anchor text signature
- optional visual anchor signature

### 5.3 Schema linkage
Stored under `schema_ref`:
- path to template schema JSON
- source blank PDF path
- optional derived assets paths

### 5.4 Runtime hints
Stored under `runtime_hints`:
- preferred extraction mode
- expected document class
- language hints
- alignment sensitivity
- fallback policy

---

## 6. Fingerprint Design

## 6.1 Metadata fingerprint
Suggested fields:
- `title`
- `producer`
- `creator`
- `subject`
- optional normalized metadata hash

This is a weak signal, useful but not enough alone.

## 6.2 AcroForm fingerprint
Suggested fields:
- field count
- normalized field name list
- field type summary
- optional widget count
- optional AcroForm hash

This is a strong signal for fillable forms like T2200.

Example:
```json
"acroform": {
  "field_count": 181,
  "field_names": [
    "Last_Name_Fill",
    "First_Name_Fill",
    "Tax_Year_Fill"
  ]
}
```

## 6.3 Page signature
Suggested fields:
- page count
- page widths/heights
- orientations
- rotation summary

## 6.4 Anchor text signature
Suggested fields:
- stable printed labels
- section headings
- key phrases expected in the form

## 6.5 Visual anchor signature
Suggested fields:
- page thumbnail hash
- anchor region hashes
- optional coarse image fingerprint

This is useful mainly for flattened/scanned forms.

---

## 7. Schema Reference Design

Each registry record should point to the canonical template schema.

Example:

```json
"schema_ref": {
  "schema_path": "templates/t2200_fill_25e/schema.json",
  "blank_pdf_path": "templates/t2200_fill_25e/t2200-fill-25e.pdf",
  "assets": {
    "page_images_dir": "templates/t2200_fill_25e/pages/",
    "anchors_path": "templates/t2200_fill_25e/anchors.json"
  }
}
```

### Recommendation
Do not duplicate full field schema inside the registry record.
Keep the registry lightweight and point to the schema artifact.

---

## 8. Runtime Hints Design

Runtime hints should help the analyzer make better extraction decisions after matching.

Suggested fields:
- `default_input_mode`: `typed`, `handwritten`, `mixed`
- `primary_language`: `en`, `fr`, etc.
- `alignment_mode`: `strict`, `normal`, `relaxed`
- `unknown_field_policy`: `review`, `fallback`, `fail`
- `preferred_extractors`: list of extractor preferences

Example:

```json
"runtime_hints": {
  "default_input_mode": "mixed",
  "primary_language": "en",
  "alignment_mode": "strict",
  "unknown_field_policy": "review",
  "preferred_extractors": [
    "native_text_first",
    "handwriting_ocr",
    "checkbox_detector"
  ]
}
```

---

## 9. Versioning Rules

Versioning is important because forms change.

### Rule 1
One materially different form layout should get a new `template_id` or a new exact version record.

### Rule 2
Minor metadata changes without layout impact should not necessarily create a new family.

### Rule 3
If field geometry changes, treat it as a new template version.

### Rule 4
Do not overwrite old template records silently.
Keep older versions queryable.

---

## 10. T2200 Example Record

```json
{
  "template_id": "t2200_fill_25e",
  "template_family": "t2200",
  "template_version": "2025-en-v1",
  "display_name": "T2200 Declaration of Conditions of Employment",
  "status": "active",
  "fingerprints": {
    "metadata": {
      "title": "Declaration of Conditions of Employment",
      "creator": "Designer 6.3"
    },
    "acroform": {
      "field_count": 181,
      "field_names": [
        "Last_Name_Fill",
        "First_Name_Fill",
        "Tax_Year_Fill",
        "Job_Title_Fill"
      ]
    },
    "page_signature": {
      "page_count": 3
    },
    "anchor_text": {
      "phrases": [
        "Declaration of Conditions of Employment",
        "Part A",
        "Part B",
        "Part C"
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

This example reflects what we observed from the real T2200 pair.

---

## 11. Storage Options

### Option A. JSON file registry
Store registry as one JSON file or several template manifest files.

Pros:
- simple
- easy for MVP
- versionable in git

Cons:
- less convenient for search at scale

### Option B. SQLite/Postgres registry
Store template registry in database tables.

Pros:
- easier queries and updates
- better at scale

Cons:
- more setup

### MVP recommendation
Use **JSON manifest files** first.
This is simpler and fits the current planning stage.

---

## 12. Suggested Directory Layout

```text
pdf-handwriting-analyze/
  templates/
    registry.json
    t2200_fill_25e/
      manifest.json
      schema.json
      t2200-fill-25e.pdf
      anchors.json
      pages/
```

### Recommendation
A per-template folder with `manifest.json` is cleaner than one giant registry file.
A top-level `registry.json` can optionally index all manifests.

---

## 13. Registry API Expectations

The analyzer should be able to ask the registry:
- list known templates
- load manifest by `template_id`
- fetch fingerprints for matching
- resolve schema path for runtime extraction

---

## 14. MVP Recommendation

For MVP, the registry should support:
- manual template registration
- per-template manifest JSON
- AcroForm fingerprint storage
- page count / size signature
- schema path resolution
- runtime hint loading

That is enough to support template-first extraction on known forms like T2200.

---

## 15. Final Recommendation

Build the template registry as a lightweight manifest-based system first.

Why:
- template matching now has something concrete to match against
- runtime extraction has a stable source of schema and hints
- T2200 already shows that AcroForm fingerprinting can be a strong registry signal
