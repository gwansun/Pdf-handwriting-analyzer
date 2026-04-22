# PDF Handwriting Analyzer - Suggested Module Layout for Template Registration and Unknown-Template Fallback

## Purpose

Define a clean file/module layout for implementing the approved behavior without changing code in this planning step.

Approved behavior:
1. blank PDF + manifest/schema already prepared -> keep as is
2. blank PDF exists only as a raw file, no template artifacts -> analyze blank PDF, generate manifest/schema, and use/register them
3. filled PDF arrives before template registration -> do not fail fast, process with `review_required`
4. unknown file (not actually PDF) -> fail fast

---

## Design goals

- preserve the current matched-template path
- keep `main.py` orchestration readable
- separate registration logic from extraction logic
- separate blank-template handling from unknown filled-form fallback
- keep registry loading as the source of truth for known templates
- keep non-PDF failure logic simple and early

---

## Recommended top-level ownership split

### `main.py`
Role:
- orchestration only
- route requests into one of the three PDF paths:
  - matched-template extraction
  - blank-template registration
  - unknown filled-PDF fallback

Should NOT own:
- template generation details
- fallback extraction details
- low-level classification heuristics

### `src/common/`
Role:
- shared primitives and infrastructure
- config, validator, inspector, response builders, core types

### `src/template/`
Role:
- template-centric workflows
- matching, registration, loading, activation, classification

### `src/extractors/`
Role:
- actual field extraction mechanics
- matched-schema routing and unknown-template provisional extraction helpers

---

## Recommended module layout

```text
src/
  common/
    config.py
    validator.py
    pdf_inspector.py
    response_builder.py
    template_registry.py
    template_matcher.py
    types.py

  template/
    __init__.py
    document_role_classifier.py
    registration.py
    manifest_builder.py
    schema_builder.py
    anchor_builder.py
    activation.py
    unknown_fallback.py
    registration_types.py

  extractors/
    field_router.py
    field_cropper.py
    normalizer.py
    glm_ocr.py
    gemma_client.py
    provisional_router.py
```

---

## Module-by-module responsibilities

## 1. `src/template/document_role_classifier.py`

### Purpose
Decide what kind of PDF was received after basic validation and inspection.

### Recommended outputs
- `blank_template_candidate`
- `filled_instance`
- `invalid_or_unsupported`
- optional confidence / reason list

### Why this should be separate
This decision is central to the new behavior and should not be buried inside `main.py` or `template_matcher.py`.

### Inputs
- validated request
- `PDFInspectionResult`
- optional field-value inspection from AcroForm
- optional future visual/document heuristics

### Output type
Prefer a small dataclass such as:
- `DocumentRoleResult(role, confidence, reasons)`

---

## 2. `src/template/registration.py`

### Purpose
Main entrypoint for blank-PDF template registration.

### Recommended responsibilities
- accept a blank/canonical PDF path
- coordinate registration stages
- call builders for manifest/schema/anchors
- create template folder
- persist generated artifacts
- trigger registry activation/reload

### Suggested public function
- `register_blank_pdf(...) -> RegistrationResult`

### Should not do
- matched-template extraction
- unknown filled-form fallback extraction

---

## 3. `src/template/manifest_builder.py`

### Purpose
Build `manifest.json` content from PDF inspection + inferred template metadata.

### Responsibilities
- identity field generation
- fingerprint assembly
- schema refs
- runtime hints
- initial status assignment (`draft` recommended)

### Why separate
Manifest generation has a clean artifact boundary and should be testable without involving full registration orchestration.

---

## 4. `src/template/schema_builder.py`

### Purpose
Build initial `schema.json` for a blank/canonical PDF.

### Responsibilities
- infer field definitions from AcroForm/widgets/layout
- create field records with bbox/page/field type/label
- produce runtime extraction schema usable later by matched-template flow

### Why separate
This will be the hardest evolving part, so it deserves isolation from orchestration logic.

---

## 5. `src/template/anchor_builder.py`

### Purpose
Generate optional anchor assets for alignment/runtime support.

### Responsibilities
- derive anchor candidates from native text/layout
- optionally emit `anchors.json`
- optionally generate page assets / debug overlays

### Recommendation
Keep this optional in MVP. Registration should still succeed without sophisticated anchors if a usable schema can be generated.

---

## 6. `src/template/activation.py`

### Purpose
Handle template post-generation status and registry visibility.

### Responsibilities
- decide `draft` vs `active`
- validate manifest/schema completeness
- refresh registry cache after registration
- prevent unsafe overwrite behavior

### Why separate
Activation policy is a lifecycle concern, not a builder concern.

---

## 7. `src/template/registration_types.py`

### Purpose
Hold dataclasses / typed structures for registration flow.

### Suggested types
- `RegistrationResult`
- `GeneratedTemplateArtifacts`
- `TemplateIdentity`
- `ArtifactWriteResult`

### Why separate
Avoid overloading existing analyzer response types with registration-specific state.

---

## 8. `src/template/unknown_fallback.py`

### Purpose
Handle valid filled PDFs that do not match a registered template.

### Responsibilities
- orchestrate provisional extraction
- call best-effort extraction helpers
- build conservative field outputs
- compute warnings and summary semantics for `review_required`

### Suggested public function
- `extract_unknown_filled_pdf(...) -> UnknownFallbackResult`

### Important rule
This module should never silently register templates.
Its job is extraction fallback, not registry mutation.

---

## 9. `src/extractors/provisional_router.py`

### Purpose
Provide field-level extraction logic for unknown filled PDFs without a schema-backed matched-template flow.

### Responsibilities
- route generic extraction attempts
- support zero-field or sparse-field outcomes
- keep conservative confidence values
- attach extraction warnings liberally

### Why in `extractors/`
Because this is still extraction logic, even though it is not schema-driven.

---

## Keep these existing modules with mostly current roles

### `src/common/template_registry.py`
Keep as the source of truth for registered templates.
Enhance it later with:
- reload helpers
- completeness validation helpers
- optional asset lookup helpers

### `src/common/template_matcher.py`
Keep focused on matching only.
Do not overload it with registration or fallback extraction decisions.

### `src/common/pdf_inspector.py`
Keep focused on PDF inspection.
It may expose a few extra signals later, but should not become a policy/orchestration module.

### `src/common/response_builder.py`
Extend carefully to support:
- unknown filled-PDF `review_required` response builder
- optional registration-event response builder if needed

---

## Recommended `main.py` dependency shape

`main.py` should eventually depend on the new modules roughly like this:

```text
validate_json_request
  -> inspect_pdf
  -> find_best_match
  -> if matched:
       load schema
       normal matched extraction
  -> else:
       classify document role
       -> blank_template_candidate:
            register_blank_pdf
       -> filled_instance:
            extract_unknown_filled_pdf
       -> invalid_or_unsupported:
            fail response
```

This keeps `main.py` as a coordinator rather than a dumping ground.

---

## File placement recommendation summary

### Add these files
- `src/template/document_role_classifier.py`
- `src/template/registration.py`
- `src/template/manifest_builder.py`
- `src/template/schema_builder.py`
- `src/template/anchor_builder.py`
- `src/template/activation.py`
- `src/template/registration_types.py`
- `src/template/unknown_fallback.py`
- `src/extractors/provisional_router.py`

### Avoid these anti-patterns
- do not put registration generation directly into `main.py`
- do not put unknown filled-PDF fallback directly into `template_matcher.py`
- do not overload `template_registry.py` with artifact-generation logic
- do not make provisional extraction silently mutate registry state

---

## Recommended implementation order for modules

1. `document_role_classifier.py`
2. `registration_types.py`
3. `registration.py`
4. `manifest_builder.py`
5. `schema_builder.py`
6. `activation.py`
7. `unknown_fallback.py`
8. `provisional_router.py`
9. light `response_builder.py` extensions
10. `main.py` orchestration wiring

---

## Final recommendation

Use a three-lane architecture:
- **matched lane** -> existing registered-template extraction
- **registration lane** -> blank PDF bootstraps manifest/schema/assets
- **fallback lane** -> unknown filled PDFs return `review_required`

That is the cleanest way to implement the approved behavior without turning the analyzer entrypoint into a tangled policy blob.
