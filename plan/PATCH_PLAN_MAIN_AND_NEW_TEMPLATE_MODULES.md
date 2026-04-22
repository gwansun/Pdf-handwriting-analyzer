# PDF Handwriting Analyzer - Patch Plan for `main.py` and New Template Modules

## Purpose

Provide a non-coding patch plan for how to evolve the current analyzer entrypoint and surrounding modules to support:
- blank-PDF auto-registration
- unknown filled-PDF review-required fallback
- continued hard fail-fast for invalid/non-PDF inputs
- preservation of the current matched-template flow

This is a planning document only.

---

## Current baseline

Current `main.py` flow is:

```text
validate request
  -> inspect PDF
  -> load registry
  -> match template
  -> if not matched: fail-fast unknown-template response
  -> if matched: load schema
  -> extract fields
  -> compute confidence
  -> return completed or review_required
```

### Current limitation
All unknown templates collapse into one behavior:
- top-level `failed`

That no longer matches the approved product policy.

---

## Desired future flow

```text
validate request
  -> inspect PDF
  -> if invalid/non-PDF: fail fast
  -> load registry
  -> match template
  -> if matched:
       normal matched-template extraction
  -> if not matched:
       classify document role
       -> blank_template_candidate:
            run template registration flow
       -> filled_instance:
            run provisional fallback extraction
            return review_required
       -> invalid_or_unsupported:
            fail safely
```

---

## Patch plan overview

The patch sequence should be done in small, low-risk steps.

### Step 1. Introduce document-role classification without changing final behavior yet
Goal:
- add the ability to distinguish blank/canonical PDFs from filled PDFs
- keep the current fail-fast behavior temporarily while classification is stabilized

#### Planned changes
- add `src/template/document_role_classifier.py`
- add a small result type such as `DocumentRoleResult`
- call classifier in `main.py` only after match failure
- initially just log classification outcome

#### Why first
This creates observability before behavior changes.

---

### Step 2. Refactor `main.py` into explicit branch helpers
Goal:
- make `main.py` easier to extend safely

#### Recommended helper split inside `main.py` or nearby modules
- `_handle_invalid_input(...)`
- `_handle_matched_template(...)`
- `_handle_unknown_pdf(...)`

#### Result
Before adding new behavior, the main entrypoint becomes structurally easier to patch.

---

### Step 3. Add blank-template registration module
Goal:
- support the case where a blank/canonical PDF exists but template artifacts do not

#### New modules
- `src/template/registration.py`
- `src/template/manifest_builder.py`
- `src/template/schema_builder.py`
- optional `src/template/anchor_builder.py`
- `src/template/registration_types.py`
- `src/template/activation.py`

#### Planned behavior
When `document_role == blank_template_candidate` and no registered template matched:
- create template folder
- write blank PDF into template folder
- generate `manifest.json`
- generate `schema.json`
- generate optional assets
- activate or mark as draft
- reload registry

#### Open design choice
Decide whether `main.py` should return:
- a dedicated registration response, or
- a `review_required` response with registration warnings, or
- a specialized success-like internal event

### Recommendation
Use a dedicated registration result internally, then map it to a clear analyzer response shape deliberately, instead of hiding it as an ambiguous extraction response.

---

### Step 4. Add unknown filled-PDF fallback module
Goal:
- replace strict fail-fast behavior for valid filled PDFs that do not match any template

#### New modules
- `src/template/unknown_fallback.py`
- `src/extractors/provisional_router.py`

#### Planned behavior
When `document_role == filled_instance` and no template match exists:
- run best-effort extraction
- build low-confidence field outputs or empty field set
- return top-level `review_required`
- include `UNKNOWN_TEMPLATE` warning
- avoid top-level `error` unless fallback extraction crashes

#### Key guardrail
Do not let fallback extraction modify the template registry.

---

### Step 5. Extend response builders cleanly
Goal:
- keep response semantics explicit and contract-compliant

#### Planned response-builder additions
- builder for unknown filled-PDF provisional review response
- optional builder for template-registration event response

#### Semantics to preserve
- matched known template -> `completed` or `review_required`
- unknown filled PDF -> `review_required`
- invalid/non-PDF -> `failed`
- blank-PDF registration -> explicit registration path, not accidental extraction failure

---

### Step 6. Update `main.py` to use the new branching model
Goal:
- wire the new modules in only after they exist and are testable in isolation

#### Concrete branch plan

1. validate request
2. inspect PDF
3. if inspection fails -> existing fail-fast failure response
4. load registry
5. match template
6. if matched -> existing matched-template extraction path
7. if not matched:
   - classify document role
   - if `blank_template_candidate` -> registration module
   - if `filled_instance` -> unknown fallback module
   - else -> safe failure response

#### Recommendation
Keep the matched-template branch byte-for-byte as stable as possible while introducing the new branches around it.

---

## Detailed patch areas

## Patch area A. `main.py`

### What to change
- split monolithic `analyze()` branching into explicit path handlers
- insert document-role classification after unknown match
- replace unconditional `build_unknown_template_response(...)` call

### What to keep stable
- request validation
- PDF inspection error handling
- registry load + match call
- matched-template extraction loop
- confidence scoring for matched-template path

### Risk
If too much is changed at once, the known-template path could regress.

### Recommendation
Refactor first, then change policy behavior second.

---

## Patch area B. `src/common/response_builder.py`

### What to add
- `build_unknown_filled_review_response(...)`
- optional `build_template_registration_response(...)`

### What to avoid
- do not overload `build_unknown_template_response(...)` with too many conditionals
- keep invalid-input `failed` behavior separate from valid-unknown-filled fallback behavior

---

## Patch area C. `src/common/template_registry.py`

### What to extend
- reload support after registration
- optional manifest/schema completeness checks
- optional helper to validate whether a template folder is usable

### What not to do
- do not put schema/manifest generation logic here

---

## Patch area D. `src/template/registration.py`

### What this patch should define
- registration orchestration contract
- folder creation strategy
- artifact write sequence
- collision handling policy
- draft-vs-active policy

### Recommended return shape
A typed result containing:
- template_id
- output folder path
- generated artifacts
- activation status
- warnings

---

## Patch area E. `src/template/unknown_fallback.py`

### What this patch should define
- provisional extraction orchestration
- warning generation
- low-confidence summary generation
- zero-field permissible behavior

### Recommended return shape
A typed result containing:
- field results
- overall confidence
- review_required flag
- warnings
- match status (`unknown` / `unmatched`)

---

## Patch area F. tests

### Test groups to add before full wiring
1. document-role classifier tests
2. blank registration tests
3. unknown filled fallback tests
4. invalid/non-PDF fail-fast tests
5. regression tests for known matched templates

### Recommended sequencing
Do not fully switch `main.py` policy until these isolated tests exist.

---

## Open design questions to settle before coding

### 1. What analyzer response should template registration return?
Options:
- dedicated registration status/event
- `review_required` with registration warning
- `completed` with empty fields and registration metadata

### Recommendation
Use a dedicated internal registration result and document how it maps externally. Do not pretend registration is a normal extraction result.

### 2. When should auto-generated templates become `active`?
Options:
- immediately active
- always draft first
- draft unless confidence/structure is very strong

### Recommendation
Start as `draft` by default for safety.

### 3. How aggressive should blank-vs-filled classification be?
### Recommendation
Bias toward safety:
- false negative blank classification is better than false positive auto-registration of filled docs

### 4. Should unknown filled fallback produce partial fields or empty fields when weak?
### Recommendation
Allow both, but always preserve `review_required` and conservative confidence.

---

## Recommended execution order

1. refactor `main.py` into clearer handlers without policy change
2. add document-role classifier and logging only
3. add registration modules and isolated tests
4. add unknown filled fallback modules and isolated tests
5. extend response builders
6. switch `main.py` unknown-template branch to the new policy
7. add regression coverage for all four approved behaviors
8. update docs if any contract details changed during implementation

---

## Definition of patch-plan success

This patch plan succeeds when implementation can proceed with:
- minimal regression risk to the known-template path
- explicit separation between registration and extraction fallback
- clear response semantics for each document type
- a stable place for future refinement without turning `main.py` into policy spaghetti
