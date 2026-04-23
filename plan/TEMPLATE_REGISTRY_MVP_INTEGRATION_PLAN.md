# PDF Analyzer Template Registry MVP Integration Plan

## 1. Purpose

Define what the PDF Analyzer side needs to expose and support for the Email Manager template registry UI feature.

This plan covers:
- what existing analyzer code is reused as-is
- what additions or wrappers are needed
- what Email Manager is allowed to depend on
- what should not change in this MVP phase

This plan assumes the Email Manager MVP plan is the product driver.
Analyzer changes exist only to serve that product feature.

---

## 2. Governing Product Decision

From the Email Manager MVP plan, the following are frozen:

- canonical registry remains in PDF Analyzer under `templates/`
- Email Manager does **not** duplicate manifest/schema storage
- MVP **list/detail** uses direct read from analyzer-owned registry
- MVP **registration** must call analyzer registration logic
- new templates start as **draft** by default
- Email Manager returns normalized frontend-facing responses
- drawer is read-only, no editing in MVP

---

## 3. Existing Analyzer Code That Is Reused As-Is

The following existing modules already provide the needed functionality:

### 3.1 `src/common/template_registry.py`
- `TemplateRegistry` class
- `load_all()` — enumerates template folders
- `get()` — returns `TemplateRecord` for one template
- `get_manifest()` — returns dict form for response serialization
- `load_schema()` — returns `TemplateSchema` for a template
- `list_active()` — returns all active template records

**Reuse:** This is the primary read path for list and detail operations.

### 3.2 `src/template/registration.py`
- `register_blank_pdf()` — main registration entrypoint
- accepts a blank PDF path and inspection result
- writes template folder, manifest.json, schema.json, blank PDF copy
- handles unique template_id generation
- returns `RegistrationResult` with success/error/artifacts

**Reuse:** This is the primary write path for template registration.

### 3.3 `src/template/registration_types.py`
- `RegistrationResult`
- `GeneratedTemplateArtifacts`
- `TemplateIdentity`
- `ArtifactWriteResult`

**Reuse:** These are the return types from registration.

### 3.4 `src/common/pdf_inspector.py`
- `PDFInspectionResult`
- `inspect_pdf()` — PDF structure inspection

**Reuse:** Required input for the registration path.

### 3.5 `src/template/schema_builder.py`
- `build_schema()` — generates schema.json from inspection

**Reuse:** Called by registration, already integrated.

### 3.6 `src/template/manifest_builder.py`
- `build_manifest()` — generates manifest.json from identity + inspection

**Reuse:** Called by registration, already integrated.

---

## 4. What Is Already Sufficient

### 4.1 Template listing
`TemplateRegistry.list_active()` already returns all active template records.
Each `TemplateRecord` already has:
- template_id
- template_family
- template_version
- display_name
- status
- created_at / updated_at (from manifest)
- runtime_hints
- fingerprints
- schema_ref

The only gap: `field_count` requires loading `schema.json` separately.

### 4.2 Template detail
`TemplateRegistry.get(template_id)` + `load_schema(template_id)` already covers the detail read path.

### 4.3 Template registration
`register_blank_pdf()` already handles the full write path:
- folder creation
- blank PDF copy
- manifest generation
- schema generation
- registry reload
- draft status by default

---

## 5. What Needs To Be Added or Wrapped

### 5.1 Entrypoint wrapper for Email Manager integration

Email Manager will invoke analyzer through a subprocess call (consistent with how the analyzer is already called for PDF analysis in Email Manager).

**Need:** A dedicated entrypoint or action-mode in the analyzer CLI that can:
- receive a JSON action envelope on stdin
- return JSON response on stdout

**Recommended approach:**
Extend `main.py` to accept an `action` field in the request envelope:

```json
{
  "action": "list_templates"
}
```

```json
{
  "action": "get_template_detail",
  "template_id": "t2200_fill_25e"
}
```

```json
{
  "action": "register_template",
  "file_path": "/absolute/path/to/blank.pdf",
  "template_family_hint": null,
  "activate": false
}
```

This keeps the analyzer CLI as the single integration boundary and avoids Email Manager needing to import analyzer Python modules directly.

### 5.2 Response normalization helpers

The raw Python return types from `TemplateRegistry` and `register_blank_pdf()` are not directly JSON-serializable in all cases.

**Need:** Helper functions to convert:
- `TemplateRecord` → normalized dict for list/detail responses
- `RegistrationResult` → normalized dict for registration response
- computed fields like `field_count` and `blank_pdf_available`

**Where to add:**
- `src/template/registry_api_helpers.py` (new file)
- or extend `src/common/template_registry.py` with `to_api_dict()` methods

### 5.3 Registration input handling

`register_blank_pdf()` currently expects:
- `pdf_path`: absolute path to blank PDF
- `inspection`: `PDFInspectionResult`
- optional `template_family_hint`

**What needs to happen before calling it from the CLI wrapper:**
- read the uploaded PDF from the temp path
- run `inspect_pdf()` to get inspection result
- pass both into `register_blank_pdf()`

This logic belongs in the CLI wrapper or a thin orchestrator function.

---

## 6. Directory and Path Assumptions

### 6.1 Templates root
The canonical templates root is:
- `templates/`

Email Manager will read from this directory directly for MVP list/detail.
This path must remain stable.

### 6.2 Per-template folder structure
```
templates/<template_id>/
  manifest.json
  schema.json
  <template_id>.pdf   (the blank PDF copy)
```

This structure must remain stable enough for Email Manager to navigate it.

### 6.3 Config or env var for templates root
To avoid hardcoding, the templates root should be configurable.

**Recommendation:**
Add a `TEMPLATES_DIR` configuration in `src/common/config.py` that defaults to the project-relative `templates/` directory.

This is already partially present but should be confirmed stable.

---

## 7. What Email Manager Is Allowed To Depend On

For this MVP, Email Manager may depend on:

### 7.1 Directory structure
- `templates/<template_id>/manifest.json` — exists for every registered template
- `templates/<template_id>/schema.json` — exists for every registered template
- `templates/<template_id>/<template_id>.pdf` — blank PDF copy (may not exist for manually created entries)

### 7.2 Manifest schema (minimum)
Email Manager can rely on these fields being present in `manifest.json`:
- `template_id`
- `template_family`
- `template_version`
- `display_name`
- `status`
- `created_at`
- `updated_at`
- `runtime_hints`
- `schema_ref.schema_path`
- `schema_ref.blank_pdf_path`

### 7.3 Registration behavior
- `register_blank_pdf()` always creates `manifest.json` and `schema.json`
- new templates start as `draft` unless `activate=True`
- `template_id` is auto-generated and unique
- `template_folder` is deterministic based on `template_id`

### 7.4 Error behavior
- registration returns `RegistrationResult` with `success=True/False`
- errors are in `errors` list
- warnings are in `warnings` list
- artifacts describe what was written

---

## 8. What Must Not Change In Analyzer MVP

These are out of scope and must not be disrupted by this integration work:

### 8.1 PDF analysis pipeline
The existing PDF analysis flow must remain working:
- `main.py` analysis entrypoint
- all template matching
- field extraction
- Gemma review integration
- confidence scoring

### 8.2 Registry read path
`TemplateRegistry` and all existing registry loading/matching behavior must remain working.

### 8.3 Template folder structure
The existing per-template folder layout must remain compatible with current extraction code.

### 8.4 Schema format
`schema.json` format must remain compatible with current field extraction code.

### 8.5 Activation workflow
Template activation / deprecation is out of scope for this MVP.
Do not add activation logic unless explicitly needed.

### 8.6 Template editing
No editing of existing templates through the analyzer CLI is in scope.
Do not add edit-mode to the registration flow.

---

## 9. Integration Contract: Actions

### Action 1. `list_templates`

**Input:**
```json
{
  "action": "list_templates"
}
```

**Output:**
```json
{
  "action": "list_templates",
  "templates": [
    {
      "template_id": "t2200_fill_25e",
      "display_name": "T2200 Declaration",
      "template_family": "t2200",
      "template_version": "2025",
      "status": "active",
      "created_at": "2026-04-20T10:00:00Z",
      "updated_at": "2026-04-20T10:00:00Z",
      "field_count": 42,
      "blank_pdf_available": true
    }
  ],
  "count": 1
}
```

### Action 2. `get_template_detail`

**Input:**
```json
{
  "action": "get_template_detail",
  "template_id": "t2200_fill_25e"
}
```

**Output:**
```json
{
  "action": "get_template_detail",
  "template_id": "t2200_fill_25e",
  "display_name": "T2200 Declaration",
  "template_family": "t2200",
  "template_version": "2025",
  "status": "active",
  "created_at": "2026-04-20T10:00:00Z",
  "updated_at": "2026-04-20T10:00:00Z",
  "runtime_hints": {
    "default_input_mode": "mixed",
    "primary_language": "en",
    "alignment_mode": "strict",
    "unknown_field_policy": "review",
    "preferred_extractors": []
  },
  "artifacts": {
    "manifest_path": "templates/t2200_fill_25e/manifest.json",
    "schema_path": "templates/t2200_fill_25e/schema.json",
    "blank_pdf_available": true
  },
  "schema": {
    "field_count": 42
  }
}
```

**Error (not found):**
```json
{
  "action": "get_template_detail",
  "error": "TEMPLATE_NOT_FOUND",
  "message": "Template t2200_fill_25e not found"
}
```

### Action 3. `register_template`

**Input:**
```json
{
  "action": "register_template",
  "file_path": "/absolute/path/to/uploaded-blank.pdf",
  "template_family_hint": null,
  "activate": false
}
```

**Output (success):**
```json
{
  "action": "register_template",
  "success": true,
  "template_id": "auto_91c05d",
  "template_folder": "templates/auto_91c05d",
  "activation_status": "draft",
  "artifacts": {
    "blank_pdf_path": "templates/auto_91c05d/auto_91c05d.pdf",
    "manifest_path": "templates/auto_91c05d/manifest.json",
    "schema_path": "templates/auto_91c05d/schema.json"
  },
  "warnings": [],
  "errors": []
}
```

**Output (failure):**
```json
{
  "action": "register_template",
  "success": false,
  "template_id": null,
  "errors": ["Failed to read PDF: ..."],
  "warnings": []
}
```

---

## 10. Error Handling

### 10.1 Template not found
Return `{"error": "TEMPLATE_NOT_FOUND", "message": "..."}`
HTTP-like error code is not needed since this is subprocess JSON I/O.

### 10.2 Registration failure
Return `{"success": false, "errors": [...]}`
Preserve all error messages from `RegistrationResult.errors`.

### 10.3 Invalid input
Validate `action` field first.
Return `{"error": "INVALID_ACTION", "message": "..."}` for unknown actions.

### 10.4 Analyzer internal error
Catch exceptions at the CLI entrypoint.
Return `{"error": "INTERNAL_ERROR", "message": "..."}`.
Do not leak raw Python tracebacks to Email Manager.

---

## 11. Key Design Decisions To Freeze

### 11.1 Subprocess CLI as integration boundary
Email Manager invokes analyzer via subprocess CLI (stdin/stdout JSON).
This is consistent with how the existing PDF analysis adapter works.

### 11.2 Action envelope pattern
One CLI entrypoint handles multiple actions via `action` field.
Avoids creating multiple CLI subcommands for MVP simplicity.

### 11.3 Templates root is stable
`TEMPLATES_DIR` is the single configuration point for template storage.
It must not be moved or become dynamic during this MVP.

### 11.4 No direct Python import from Email Manager
Email Manager must not import analyzer Python modules directly.
All interaction goes through the CLI subprocess boundary.
This preserves clean separation.

### 11.5 New templates are draft by default
`register_blank_pdf()` already defaults to draft.
No change needed.

### 11.6 Email Manager does not write to templates/
The CLI wrapper passes an absolute file path to registration.
Analyzer writes canonical artifacts.
Email Manager only reads, never writes, to the templates directory.

---

## 12. Non-Goals For This MVP

These are explicitly out of scope:

- template activation workflow
- template editing or deletion
- template versioning UI
- analyzer-side template management UI
- moving or restructuring the templates directory
- changing the PDF analysis pipeline
- adding a HTTP server to the analyzer
- direct Python import of analyzer modules from Email Manager

---

## 13. Summary

The analyzer side for this MVP is intentionally minimal:
- **reuse** existing registry and registration code
- **add** a CLI action envelope wrapper
- **add** response normalization helpers
- **preserve** all existing analysis behavior
- **expose** only list/detail/register actions
- **keep** templates/ as the stable source of truth

No registry redesign. No storage changes. No analysis pipeline changes.