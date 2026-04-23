# PDF Analyzer Template Registry MVP Coding Checklist

## Purpose

Implementation checklist for the PDF Analyzer side of the Email Manager template registry MVP feature.

Grounded in:
- `plan/TEMPLATE_REGISTRY_MVP_INTEGRATION_PLAN.md`
- `plan/TEMPLATE_REGISTRY_DESIGN.md`
- `plan/MINIMUM_MANIFEST_SCHEMA.md`

---

## Locked MVP Decisions

- canonical registry remains in PDF Analyzer under `templates/`
- Email Manager does **not** duplicate manifest/schema storage
- MVP **list/detail** uses direct read from analyzer-owned registry
- MVP **registration** must call analyzer registration logic
- Email Manager invokes analyzer via **subprocess CLI boundary only**
- new templates start as **draft** by default
- **no template editing** in MVP
- **no activation workflow** in MVP
- **no HTTP server** addition to analyzer

---

## Phase 1. Config stability

### 1.1 Confirm TEMPLATES_DIR is configurable
- [ ] `src/common/config.py` has `TEMPLATES_DIR` defined
- [ ] `TEMPLATES_DIR` defaults to project-relative `templates/`
- [ ] Existing `TemplateRegistry` uses this config value

### 1.2 Confirm no hardcoded paths
- [ ] No module hardcodes a literal `templates/` path outside of config
- [ ] All template path lookups go through `TEMPLATES_DIR`

---

## Phase 2. Response normalization helpers

### 2.1 Add template list normalization
- [ ] Add helper to convert `TemplateRecord` → list-row dict
- [ ] Include: template_id, display_name, template_family, template_version, status, created_at, updated_at
- [ ] Include: computed field_count (from schema fields array length)
- [ ] Include: blank_pdf_available (from schema_ref.blank_pdf_path existence check)

### 2.2 Add template detail normalization
- [ ] Add helper to convert `TemplateRecord` → detail dict
- [ ] Include: all list-row fields
- [ ] Include: runtime_hints block
- [ ] Include: artifacts block with paths and availability
- [ ] Include: schema summary (field_count only for MVP)

### 2.3 Add registration response normalization
- [ ] Add helper to convert `RegistrationResult` → API response dict
- [ ] Map `success` field
- [ ] Map `template_id`, `template_folder`
- [ ] Map `activation_status`
- [ ] Map `artifacts` from `GeneratedTemplateArtifacts`
- [ ] Map `warnings` and `errors` lists

### 2.4 Add error response helpers
- [ ] Add helper for not-found responses
- [ ] Add helper for invalid-action responses
- [ ] Add helper for internal-error responses
- [ ] Ensure no raw tracebacks leak to stdout

---

## Phase 3. CLI action envelope wrapper

### 3.1 Extend main.py to handle action envelope
- [ ] Read JSON from stdin (consistent with existing analysis entry)
- [ ] Parse `action` field
- [ ] Dispatch to appropriate handler function
- [ ] Return JSON response to stdout
- [ ] Handle unknown action gracefully

### 3.2 Implement `list_templates` action handler
- [ ] Call `TemplateRegistry.list_active()`
- [ ] Normalize each record with list-row helper
- [ ] Return `list_templates` response envelope
- [ ] Handle registry load failure gracefully

### 3.3 Implement `get_template_detail` action handler
- [ ] Parse `template_id` from request
- [ ] Call `TemplateRegistry.get(template_id)`
- [ ] Return not-found if template does not exist
- [ ] Load schema if template found
- [ ] Normalize with detail helper
- [ ] Return `get_template_detail` response envelope

### 3.4 Implement `register_template` action handler
- [ ] Parse `file_path`, `template_family_hint`, `activate` from request
- [ ] Validate `file_path` is a real file
- [ ] Run `inspect_pdf()` to get inspection result
- [ ] Call `register_blank_pdf()` with inspection result
- [ ] Normalize with registration response helper
- [ ] Return `register_template` response envelope

### 3.5 Handle registration pre-check failures
- [ ] Missing file → return registration failure
- [ ] Unreadable PDF → return registration failure with clear message
- [ ] Corrupted PDF → return registration failure with clear message

### 3.6 Confirm existing analysis entry still works
- [ ] Existing analysis `main.py` behavior is unaffected
- [ ] The action envelope is additive, not a breaking change
- [ ] Run existing smoke test or fixture if available

---

## Phase 4. Error handling and safety

### 4.1 Path safety
- [ ] `template_id` values used in paths are sanitized (no path traversal)
- [ ] File paths passed to registration are validated as absolute
- [ ] Templates directory is not writable by Email Manager process by default

### 4.2 Exception handling at CLI boundary
- [ ] All exceptions caught at top-level action dispatcher
- [ ] Return `INTERNAL_ERROR` response on unexpected exceptions
- [ ] Log exception details server-side only

### 4.3 Input validation
- [ ] `action` field must be present and known
- [ ] `template_id` must be present for `get_template_detail`
- [ ] `file_path` must be present and valid for `register_template`

---

## Phase 5. Testing

### 5.1 Unit tests for normalization helpers
- [ ] Test list-row normalization with known template
- [ ] Test detail normalization with known template
- [ ] Test field_count computation from schema
- [ ] Test blank_pdf_available computation

### 5.2 Unit tests for action handlers
- [ ] Test list_templates with no templates
- [ ] Test list_templates with known templates
- [ ] Test get_template_detail with valid template_id
- [ ] Test get_template_detail with invalid template_id
- [ ] Test register_template with valid blank PDF
- [ ] Test register_template with invalid file
- [ ] Test register_template with missing file

### 5.3 Integration smoke test
- [ ] Full subprocess call for list_templates
- [ ] Full subprocess call for get_template_detail
- [ ] Full subprocess call for register_template with valid input
- [ ] Confirm output is valid JSON

---

## Phase 6. Verify no regression in existing code

### 6.1 PDF analysis pipeline
- [ ] Existing analysis entry point still works
- [ ] Template matching still works
- [ ] Field extraction still works
- [ ] Gemma review still works

### 6.2 Registry behavior
- [ ] `TemplateRegistry.load_all()` still works
- [ ] `TemplateRegistry.get()` still works
- [ ] `TemplateRegistry.load_schema()` still works
- [ ] Existing templates still load correctly

### 6.3 Registration behavior
- [ ] `register_blank_pdf()` still works with direct Python call
- [ ] New registration creates correct folder structure
- [ ] New registration creates valid manifest.json
- [ ] New registration creates valid schema.json

---

## Phase 7. Final MVP verification

### 7.1 End-to-end from Email Manager perspective
- [ ] Email Manager can call analyzer CLI with `list_templates` action
- [ ] Email Manager receives valid JSON list response
- [ ] Email Manager can call analyzer CLI with `get_template_detail` action
- [ ] Email Manager receives valid JSON detail response
- [ ] Email Manager can call analyzer CLI with `register_template` action
- [ ] Analyzer creates canonical template folder and artifacts
- [ ] Email Manager receives valid registration response

### 7.2 Confirm split responsibilities hold
- [ ] Email Manager did not write any manifest/schema directly
- [ ] Email Manager did not import analyzer Python modules directly
- [ ] All interaction went through subprocess CLI boundary
- [ ] Templates directory remains the single source of truth

---

## Nice-to-have, not MVP

- [ ] explicit HTTP API server for analyzer (not subprocess)
- [ ] template activation/deprecation workflow
- [ ] template editing workflow
- [ ] template deletion workflow
- [ ] template search/filter in analyzer
- [ ] schema field detail in analyzer CLI output
- [ ] pagination for large template lists
- [ ] template versioning UI or controls

---

## Final rule

Build in this order:
1. config stability confirmation
2. response normalization helpers
3. CLI action envelope
4. error handling
5. unit tests
6. smoke tests
7. regression verification

Do not change the analysis pipeline. Do not add HTTP server. Do not let Email Manager write to templates/.