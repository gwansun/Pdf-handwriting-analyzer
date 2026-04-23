# Review Note - Gemma Whole-PDF Implementation (2026-04-22)

## Review result
**Status: changes not accepted yet**

The overall direction is right, but the current implementation still has blocking issues and does not fully satisfy the locked design.

## Blocking issues

### 1. Broken unknown-template fallback calls in `main.py`
`extract_unknown_filled_pdf(...)` is being called with the wrong arguments.

#### Current function signature
- `src/template/unknown_fallback.py`
  - `extract_unknown_filled_pdf(pdf_path, inspection, request_id, job_id, registry=None)`

#### Current call shape seen in `main.py`
- called with `glm_available=...`

#### Problem
- `glm_available` is not a valid parameter for that function
- this will raise a runtime `TypeError`
- unknown-template / fallback flow is currently broken

#### Required fix
- update `main.py` call sites to match the real function signature
- pass `request_id` and `job_id` correctly
- verify fallback lane executes end-to-end

---

### 2. Fallback/no-schema Gemma review path is still not implemented
The locked requirement was:

- Gemma whole-document review for:
  1. matched-template path
  2. fallback/no-schema path

#### What is implemented now
- `main.py` invokes `review_document_extraction(...)` only in matched-template flow

#### What is missing
- no actual runtime wiring for Gemma review in unknown-template / no-schema flow
- `unknown_fallback.py` currently does not invoke Gemma whole-document review

#### Required fix
- add document-level Gemma review support in fallback/no-schema flow
- ensure fallback payload is actually built and sent
- ensure one PDF still triggers at most one Gemma call

---

### 3. `gemma_client.py` reads average confidence from the wrong payload location
#### Current behavior
Payload builders store:
- `payload["document"]["average_document_confidence"]`

Prompt builders read:
- `payload.get("average_document_confidence", 0.0)`

#### Affected functions
- `_matched_template_prompt(...)`
- `_fallback_prompt(...)`

#### Problem
- Gemma prompt likely receives incorrect average confidence, often `0.00`

#### Required fix
- read confidence from `payload["document"]["average_document_confidence"]`
- confirm prompt content matches actual payload shape

---

### 4. `field_router.py` still has a handwritten extraction signature mismatch
#### Problem
The caller and callee do not match for `_extract_handwritten(...)`.

Current review found:
- caller passes 5 args
- function definition still expects 6, including `gemma_available`

#### Risk
- runtime `TypeError`
- handwritten extraction path may break

#### Required fix
- make caller and function definition consistent
- remove any leftover `gemma_available` dependency from field routing if Gemma is now document-level only

---

## Design/semantics issue to resolve

### 5. Final `review_required` logic in `main.py` may contradict the locked rule
`compute_document_confidence(...)` now correctly uses:
- average document confidence `< 0.70`

But `main.py` later does:
- `review_required = review_required or any(fr.review_required for fr in field_results)`

#### Concern
This partially reintroduces field-level review semantics into the final document status.

#### Required decision
Clarify one of these and implement consistently:

**Option A, recommended**
- Gemma trigger and final document `review_required` both follow average document confidence
- field-level `review_required` is informational only

**Option B**
- Gemma trigger follows average document confidence
- final document status may still be elevated by field-level flags

If Option B is intended, document it explicitly in plan/docs and tests.

---

## Cleanup issues

### 6. Remove leftover debug output
Examples seen in `field_router.py`:
- `DEBUG route_and_extract`
- `DEBUG _extract_typed called`

#### Required fix
- remove debug stderr prints before acceptance

---

## What looks correct
These parts look aligned with the intended design:

- first-pass `value` is preserved
- first-pass `confidence` is preserved
- Gemma output is attached separately in `review`
- response serialization includes `review`
- Gemma response parsing is reasonably defensive

---

## Required tests before acceptance

Add focused tests for the new behavior:

### Matched-template tests
- matched PDF with average confidence `< 0.70` → exactly one Gemma call
- matched PDF with average confidence `>= 0.70` → zero Gemma calls
- many low-confidence fields in one document → still exactly one Gemma call

### Fallback/no-schema tests
- unknown/no-schema PDF with average confidence `< 0.70` → exactly one fallback Gemma call
- fallback review path returns safely when template metadata is unavailable

### Failure-handling tests
- Gemma unavailable → pipeline degrades safely
- malformed Gemma JSON → pipeline degrades safely
- first-pass `value` and `confidence` remain unchanged after review merge

---

## Acceptance criteria
Please consider the change ready only when:

- unknown-template fallback path runs without argument/signature errors
- fallback/no-schema Gemma review is actually wired in runtime
- Gemma prompt uses correct average document confidence
- no per-field Gemma invocation remains
- one document triggers at most one Gemma call
- first-pass `value` and `confidence` remain preserved
- tests cover matched and fallback whole-document review paths
