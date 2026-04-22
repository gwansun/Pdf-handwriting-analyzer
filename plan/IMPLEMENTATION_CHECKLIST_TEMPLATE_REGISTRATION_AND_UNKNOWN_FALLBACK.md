# PDF Handwriting Analyzer - Implementation Checklist for Template Registration and Unknown-Template Fallback

## Purpose

Turn the approved behavior into a concrete implementation checklist.

Approved behavior:
1. blank PDF + manifest/schema already prepared -> keep as is
2. blank PDF exists only as a raw file, no template artifacts -> analyze blank PDF, generate manifest/schema, and use/register them
3. filled PDF arrives before template registration -> do not fail fast, process with `review_required`
4. unknown file (not actually PDF) -> fail fast

---

## Phase 0. Guard the existing matched-template path

- [ ] Keep current matched-template runtime flow unchanged for already-registered templates
- [ ] Keep `TemplateRegistry` folder-based loading as the source of truth
- [ ] Keep non-PDF / unreadable-file validation as hard-fail behavior
- [ ] Add regression tests proving existing registered-template flow still works

---

## Phase 1. Distinguish blank/canonical PDFs from filled PDFs

- [ ] Define a `document_role` classification step before unknown-template handling:
  - [ ] `blank_template_candidate`
  - [ ] `filled_instance`
  - [ ] `invalid_or_unsupported`
- [ ] Implement first-pass heuristics for blank/canonical detection, using signals such as:
  - [ ] high AcroForm presence
  - [ ] mostly empty field values
  - [ ] strong native text / form structure
  - [ ] low evidence of handwritten/filled content
- [ ] Ensure this classifier is conservative, preferring `filled_instance` over accidentally auto-registering noisy documents as templates
- [ ] Add tests for:
  - [ ] known blank form
  - [ ] clearly filled form
  - [ ] malformed/non-PDF input

---

## Phase 2. Template auto-registration from raw blank PDFs

### 2.1 Registration entrypoint
- [ ] Create a dedicated registration module/service, for example:
  - [ ] `src/template/registration.py`
- [ ] Add a clear function such as:
  - [ ] `register_blank_pdf(file_path) -> RegistrationResult`
- [ ] Ensure normal inference runtime can call this only when document_role is `blank_template_candidate`

### 2.2 Template ID and folder creation
- [ ] Define deterministic or reviewable template-id generation
- [ ] Create template folder under:
  - [ ] `templates/<template_id>/`
- [ ] Copy/store the blank PDF into the template folder
- [ ] Prevent accidental overwrite of an existing active template without explicit policy

### 2.3 Manifest generation
- [ ] Generate `manifest.json`
- [ ] Populate:
  - [ ] identity fields
  - [ ] metadata fingerprint
  - [ ] AcroForm fingerprint
  - [ ] page signature
  - [ ] anchor text fingerprint
  - [ ] schema reference
  - [ ] runtime hints
  - [ ] initial status (`draft` recommended)

### 2.4 Schema generation
- [ ] Generate initial `schema.json`
- [ ] Infer field definitions from:
  - [ ] AcroForm fields when present
  - [ ] widget rectangles when available
  - [ ] page geometry
  - [ ] label/anchor proximity
- [ ] Include at minimum:
  - [ ] field_name
  - [ ] field_label
  - [ ] field_type
  - [ ] page number
  - [ ] bbox
  - [ ] optional validation/runtime hints

### 2.5 Optional assets
- [ ] Generate `anchors.json` if supported
- [ ] Optionally render page assets into `pages/`
- [ ] Store enough debug artifacts to review bad auto-generated templates

### 2.6 Registry activation
- [ ] Make newly generated template loadable by `TemplateRegistry`
- [ ] Decide activation policy:
  - [ ] start as `draft`
  - [ ] require light review before `active`
- [ ] Add reload behavior or cache refresh after registration

### 2.7 Tests
- [ ] Add tests proving a raw blank PDF with no artifacts can generate:
  - [ ] template folder
  - [ ] manifest.json
  - [ ] schema.json
- [ ] Add tests for registration collision / duplicate template handling
- [ ] Add tests for invalid blank PDFs

---

## Phase 3. Unknown filled-PDF fallback path

### 3.1 Fallback control flow
- [ ] Replace strict fail-fast unknown-template behavior for valid filled PDFs
- [ ] If no registered template match exists and document_role is `filled_instance`:
  - [ ] route into provisional extraction
  - [ ] do not return top-level `failed` by default

### 3.2 Provisional extraction path
- [ ] Create a dedicated fallback extractor path, for example:
  - [ ] `src/template/unknown_fallback.py`
- [ ] Support best-effort extraction without template schema
- [ ] Keep output conservative and warning-heavy
- [ ] Allow zero-field output when extraction is too weak

### 3.3 Response contract for unknown filled PDFs
- [ ] Return top-level:
  - [ ] `status = review_required`
- [ ] Set summary fields conservatively:
  - [ ] `template_match_status = "unknown"` or `"unmatched"`
  - [ ] `template_id = null`
  - [ ] low `overall_confidence`
  - [ ] `review_required = true`
- [ ] Include warning:
  - [ ] `UNKNOWN_TEMPLATE`
  - [ ] explain provisional extraction was used
- [ ] Avoid top-level `error` unless fallback extraction itself crashes

### 3.4 Tests
- [ ] Add tests for unknown but valid filled PDF -> `review_required`
- [ ] Add tests for:
  - [ ] zero extracted fields
  - [ ] partial extracted fields
  - [ ] low-confidence output
- [ ] Verify response shape stays contract-compliant

---

## Phase 4. Preserve hard fail-fast for invalid/non-PDF inputs

- [ ] Keep request validation and PDF inspection hard-fail behavior
- [ ] Return structured failure for:
  - [ ] `NOT_A_PDF`
  - [ ] `UNREADABLE_FILE`
  - [ ] `UNSUPPORTED_ENCRYPTION`
- [ ] Ensure non-PDF files never enter:
  - [ ] registration workflow
  - [ ] provisional fallback extraction
- [ ] Add explicit tests for these hard-fail cases

---

## Phase 5. Main analyzer orchestration changes

- [ ] Update `main.py` orchestration flow to branch like this:

```text
validate request
  -> inspect PDF
  -> if invalid/non-PDF: fail fast
  -> try template match
  -> if matched: normal matched-template flow
  -> if not matched:
       -> classify blank vs filled
       -> if blank_template_candidate: run registration workflow
       -> if filled_instance: run provisional fallback and return review_required
       -> otherwise: fail safely
```

- [ ] Decide response shape for successful template registration events
- [ ] Decide whether registration should:
  - [ ] return a dedicated registration response
  - [ ] or remain an internal side effect plus warning/status
- [ ] Ensure logging clearly distinguishes:
  - [ ] matched extraction
  - [ ] blank template registration
  - [ ] unknown filled fallback
  - [ ] invalid input failure

---

## Phase 6. Template registry enhancements

- [ ] Add helper to check whether a raw blank PDF already has a registered template
- [ ] Add helper to reload registry after template generation
- [ ] Add helper to load optional assets:
  - [ ] blank PDF path
  - [ ] anchors
  - [ ] page assets
- [ ] Add validation for manifest/schema completeness before activation

---

## Phase 7. Review status / product semantics

- [ ] Align top-level analyzer statuses with the approved product policy
- [ ] Keep these semantics clear:
  - [ ] known template match -> `completed` or `review_required`
  - [ ] unknown filled PDF -> `review_required`
  - [ ] invalid/non-PDF -> `failed`
  - [ ] blank PDF registration -> registration event or explicit registration success path
- [ ] Ensure downstream Email Manager behavior is documented for each case

---

## Phase 8. Documentation updates

- [ ] Keep these docs aligned with implementation:
  - [ ] `plan/UNKNOWN_TEMPLATE_POLICY.md`
  - [ ] `plan/TEMPLATE_REGISTRATION_WORKFLOW.md`
  - [ ] `plan/TEMPLATE_REGISTRY_DESIGN.md`
  - [ ] `plan/MATCHED_TEMPLATE_RUNTIME_FLOW.md`
- [ ] Add a short runtime architecture note describing the three-path split:
  - [ ] matched template
  - [ ] blank-template registration
  - [ ] unknown filled fallback

---

## Phase 9. Definition of done

Done means:
- [ ] registered templates still work exactly as before
- [ ] raw blank PDFs can generate template artifacts automatically
- [ ] generated template artifacts are stored under `templates/<template_id>/`
- [ ] unknown filled PDFs no longer fail fast by default
- [ ] unknown filled PDFs return `review_required`
- [ ] non-PDF inputs still fail fast
- [ ] regression tests cover all four approved behaviors

---

## Recommended implementation order

1. document-role classifier
2. blank-PDF registration module
3. manifest/schema generation
4. registry reload + activation rules
5. unknown filled-PDF fallback extraction path
6. main.py orchestration branch update
7. response-contract cleanup
8. tests and docs alignment
