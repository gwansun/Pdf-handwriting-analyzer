# PDF Handwriting Analyzer - Execution Brief for Template Registration and Unknown-Template Fallback

## Purpose

Provide one concise execution brief that unifies:
- the approved product behavior
- the implementation checklist
- the suggested module layout
- the patch plan centered on `main.py`

This is a planning document only. No code changes are described here as already completed.

---

## Approved behavior

The analyzer should implement these four rules:

1. **Blank PDF + manifest/schema already prepared**
   - keep current behavior
   - use the existing matched-template flow

2. **Blank PDF exists only as a raw file, with no template artifacts**
   - analyze the blank PDF
   - generate template artifacts such as `manifest.json` and `schema.json`
   - save them into the template folder
   - register/use them for future matching

3. **Filled PDF arrives before template registration exists**
   - do not fail fast just because the template is unknown
   - attempt provisional extraction
   - return `review_required`
   - keep confidence conservative and warnings explicit

4. **Unknown file, not actually a PDF**
   - fail fast
   - do not attempt registration or provisional extraction

---

## Current baseline

The current analyzer already supports:
- request validation
- PDF inspection
- template registry loading from `templates/<template_id>/manifest.json`
- template matching
- matched-template extraction using loaded `schema.json`
- completed vs `review_required` responses on matched templates

The current gap is in unknown-template handling:
- all unmatched templates currently collapse to fail-fast unknown-template response
- blank-PDF auto-registration is planned but not implemented
- unknown filled-PDF fallback is planned but not implemented

---

## Desired runtime architecture

Use a **three-lane PDF architecture** after validation/inspection:

### Lane 1. Matched-template lane
Use when a registered template is successfully matched.

Behavior:
- load manifest/schema
- run existing extraction flow
- return `completed` or `review_required`

### Lane 2. Blank-template registration lane
Use when the input is a valid blank/canonical PDF but no template artifacts exist yet.

Behavior:
- classify document as blank template candidate
- generate template folder artifacts
- register/reload template
- keep this as a registration workflow, not a normal extraction failure

### Lane 3. Unknown filled-PDF fallback lane
Use when the input is a valid filled PDF but no template matches.

Behavior:
- run provisional best-effort extraction
- return top-level `review_required`
- preserve unknown/unmatched template status in summary/warnings

### Outside the lanes
Non-PDF / invalid / unreadable input stays in hard-fail behavior.

---

## Recommended high-level flow

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
            register blank template
       -> filled_instance:
            provisional fallback extraction
            return review_required
       -> invalid_or_unsupported:
            fail safely
```

---

## Document-role classification

A classifier should be introduced before unknown-template handling changes behavior.

### Recommended roles
- `blank_template_candidate`
- `filled_instance`
- `invalid_or_unsupported`

### Recommended signals
- AcroForm presence and structure
- likely emptiness of form fields
- page structure and native text stability
- evidence of handwritten/filled content
- conservative bias toward avoiding false auto-registration of filled docs

### Policy recommendation
Prefer false negatives over false positives:
- it is safer to miss a blank candidate than to accidentally register a filled document as a template

---

## Suggested module/file layout

### Keep existing responsibilities stable
- `main.py` -> orchestration only
- `src/common/template_registry.py` -> registry loading and schema access
- `src/common/template_matcher.py` -> matching only
- `src/common/pdf_inspector.py` -> PDF inspection only
- `src/common/response_builder.py` -> response assembly

### Add these modules

```text
src/template/
  document_role_classifier.py
  registration.py
  manifest_builder.py
  schema_builder.py
  anchor_builder.py
  activation.py
  registration_types.py
  unknown_fallback.py

src/extractors/
  provisional_router.py
```

### Why this split
- avoids turning `main.py` into a policy blob
- keeps registration logic separate from extraction fallback logic
- keeps registry and matcher focused on their original roles

---

## Main implementation tracks

## Track A. Preserve existing matched-template behavior
This is the stable baseline and should be protected from regression.

### Must remain true
- already-registered templates still work exactly as before
- matched-template extraction remains the main happy path
- completed/review-required behavior for known templates does not regress

---

## Track B. Blank-PDF auto-registration

### Goal
If a valid blank/canonical PDF exists without manifest/schema, generate the missing template artifacts automatically.

### Outputs
- `templates/<template_id>/manifest.json`
- `templates/<template_id>/schema.json`
- optional `anchors.json`
- stored blank PDF
- optional page/debug assets

### Activation recommendation
- auto-generated templates should normally start as `draft`
- light review can later promote them to `active`

### Guardrail
Do not auto-register arbitrary unknown PDFs unless blank/canonical confidence is sufficiently high.

---

## Track C. Unknown filled-PDF fallback

### Goal
If a valid filled PDF arrives before a template is registered, do not hard fail-fast by default.

### Required behavior
- run best-effort extraction
- return `status = review_required`
- use conservative summary values
- attach `UNKNOWN_TEMPLATE` warning
- allow zero-field or sparse-field outputs

### Important rule
Fallback extraction must not silently mutate the template registry.
It is an extraction path, not a registration path.

---

## Track D. Keep hard fail-fast for invalid/non-PDF input

### Must remain true
- invalid files fail fast
- unreadable files fail fast
- non-PDF inputs fail fast
- unsupported encrypted PDFs fail fast
- these files must not enter registration or fallback extraction paths

---

## `main.py` patch strategy

`main.py` should be changed in small steps.

### Recommended sequence
1. refactor `main.py` into clearer branch helpers without changing policy yet
2. add document-role classification and logging only
3. add blank-template registration modules and isolated tests
4. add unknown filled fallback modules and isolated tests
5. extend response builders carefully
6. switch unknown-template branch from unconditional fail-fast to the new policy
7. add regression coverage across all four approved behaviors

### Key recommendation
Keep the existing matched-template branch as stable as possible while introducing the new branches around it.

---

## Response semantics

## Known matched template
- top-level `completed` or `review_required`

## Unknown filled PDF
- top-level `review_required`
- summary should keep unknown/unmatched template semantics
- warnings should explain provisional extraction was used
- top-level `error` should appear only if fallback extraction itself crashes

## Blank PDF registration
This should be treated as a registration workflow, not disguised as a normal extraction failure.

### Open design choice
Need to decide whether blank-template registration returns:
- a dedicated registration response/event,
- or a response shape wrapped into the analyzer contract with explicit registration semantics.

### Recommendation
Use a dedicated internal registration result and map it deliberately to the external response contract.

## Invalid / non-PDF input
- top-level `failed`
- structured error details

---

## Test strategy

### Required test groups
1. regression tests for known registered-template flow
2. document-role classifier tests
3. blank-template registration tests
4. unknown filled-PDF fallback tests
5. invalid/non-PDF fail-fast tests

### Key success conditions
- current happy path does not regress
- raw blank PDFs can generate template artifacts
- generated artifacts are stored in template folder
- unknown filled PDFs return `review_required`
- invalid inputs still fail fast

---

## Open design questions to settle before coding

1. **What external response should blank-template registration produce?**
   - recommendation: explicit registration semantics, not disguised extraction output

2. **When should auto-generated templates become active?**
   - recommendation: start as `draft`

3. **How conservative should blank-vs-filled classification be?**
   - recommendation: conservative enough to avoid accidental registry poisoning

4. **Should unknown filled fallback allow partial fields?**
   - recommendation: yes, but always low-confidence and `review_required`

---

## Recommended file reading order for implementation

1. `plan/IMPLEMENTATION_CHECKLIST_TEMPLATE_REGISTRATION_AND_UNKNOWN_FALLBACK.md`
2. `plan/SUGGESTED_MODULE_LAYOUT_TEMPLATE_REGISTRATION_AND_UNKNOWN_FALLBACK.md`
3. `plan/PATCH_PLAN_MAIN_AND_NEW_TEMPLATE_MODULES.md`
4. this file, `plan/EXECUTION_BRIEF_TEMPLATE_REGISTRATION_AND_UNKNOWN_FALLBACK.md`

Or, if someone wants the short version first:
1. this execution brief
2. the checklist
3. the patch plan
4. the module layout doc

---

## Final recommendation

Implement this as a controlled extension of the current analyzer, not a rewrite.

Use the following principle:
- **matched known template** -> existing path
- **blank unknown PDF** -> registration path
- **filled unknown PDF** -> fallback extraction path
- **invalid/non-PDF** -> fail-fast path

That keeps the product behavior aligned with the approved policy while preserving the strongest parts of the current analyzer architecture.
