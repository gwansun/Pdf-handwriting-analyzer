# Coding Checklist - Gemma Whole-PDF Review

## Purpose

Turn the Gemma whole-document review plan into an implementation checklist that can be executed directly in code.

This checklist assumes the design direction is already locked:
- GLM-OCR remains per handwritten field
- Gemma becomes one-shot per PDF
- Gemma trigger is `any(fr.review_required for fr in field_results)`
- Gemma review must work both:
  - with matched manifest/schema metadata
  - without manifest/schema metadata

---

## Definition of done

Implementation is done when:
- Gemma is never called from per-field extraction routing
- GLM-OCR still runs per handwritten field
- one PDF triggers at most one Gemma review call
- field-level `review_required` controls Gemma review triggering
- Gemma works for both matched-template and fallback/no-schema paths
- response preserves first-pass `value` and `confidence`
- review output is attached separately
- tests prove one-call-per-document behavior and safe fallback handling

---

## Phase 0. Lock interfaces before coding

- [ ] Confirm `any(fr.review_required for fr in field_results)` is the review trigger
- [ ] Confirm Gemma review must work even when manifest/schema metadata is unavailable
- [ ] Confirm response policy:
  - [ ] keep first-pass `value`
  - [ ] keep first-pass `confidence`
  - [ ] attach Gemma review output separately in `review`
- [ ] Confirm Gemma response should be structured JSON, not free-form text parsing

---

## Phase 1. Remove per-field Gemma behavior

### `src/extractors/field_router.py`

- [ ] Remove direct per-field Gemma invocation from `_extract_handwritten(...)`
- [ ] Remove dependency on `review_extraction(...)` inside handwritten extraction flow
- [ ] Keep first-pass handwritten extraction behavior intact
- [ ] Preserve field-level `review_required` signaling for downstream document-level review logic
- [ ] Ensure router remains extraction-only, not review orchestration

### Cleanup
- [ ] Remove stale comments that imply Gemma runs per field
- [ ] Remove unused imports related to per-field Gemma review
- [ ] Verify handwritten extraction still works when Gemma is unavailable

---

## Phase 2. Add document-level Gemma client

### `src/extractors/gemma_client.py`

- [ ] Add a new function for document-level review, e.g.:
  - [ ] `review_document_extraction(...)`
- [ ] Support two payload modes:
  - [ ] `matched_template_review`
  - [ ] `fallback_review`
- [ ] Build OpenAI-compatible request payload for Gemma
- [ ] Require structured JSON output from Gemma
- [ ] Parse and validate Gemma JSON safely
- [ ] Handle malformed/partial Gemma responses gracefully
- [ ] Return a structured result object, not ad-hoc tuples

### JSON contract
- [ ] Define required response keys:
  - [ ] `reviewed_fields`
  - [ ] optional `document_notes`
- [ ] Validate `field_name` presence for each reviewed field
- [ ] Validate reviewed field payload shape:
  - [ ] `reviewed_value`
  - [ ] optional `reviewed_confidence`
  - [ ] optional `reasoning`

---

## Phase 3. Add payload builders

### New helper(s)
- [ ] Add helper to build matched-template Gemma payload
- [ ] Add helper to build fallback/no-schema Gemma payload

### Matched-template payload must include
- [ ] `template_id`
- [ ] `template_family`
- [ ] `display_name`
- [ ] `template_version`
- [ ] runtime hints
- [ ] full schema field definitions
- [ ] first-pass extraction results
- [ ] document confidence summary
- [ ] review target field list

### Fallback payload must include
- [ ] request/job ids when available
- [ ] page count
- [ ] PDF metadata
- [ ] inspection signals
- [ ] AcroForm names/values when available
- [ ] page text snippets when available
- [ ] provisional extraction results when available
- [ ] document confidence summary
- [ ] warnings/classification context

---

## Phase 4. Add orchestration in `main.py`

### After first-pass extraction
- [ ] Compute document confidence summary for context
- [ ] Build review target field list
- [ ] Branch on Gemma trigger:
  - [ ] if no fields are `review_required` -> skip Gemma
  - [ ] if any field is `review_required` -> run one Gemma review pass

### Review-mode selection
- [ ] If matched template + schema loaded successfully -> use matched-template review payload
- [ ] If manifest/schema unavailable but review still needed -> use fallback review payload

### Merge step
- [ ] Merge Gemma outputs into field results
- [ ] Preserve original first-pass `value`
- [ ] Preserve original first-pass `confidence`
- [ ] Add `review` output separately
- [ ] Optionally attach `review_reasoning` internally or in response shape if enabled

### Summary recomputation
- [ ] Recompute document summary after merge
- [ ] Ensure `review_required` follows field-level trigger policy
- [ ] Ensure response status remains conservative when review was triggered

---

## Phase 5. Update response/data models

### `src/common/types.py` or response helpers
- [ ] Confirm field response shape supports `review`
- [ ] Add optional review fields if needed:
  - [ ] `review`
  - [ ] `review_reasoning`
  - [ ] `review_confidence`
- [ ] Ensure response builders preserve backward compatibility where possible

### `src/common/response_builder.py`
- [ ] Support review-enriched field responses
- [ ] Ensure `completed` vs `review_required` behavior still matches policy
- [ ] Ensure fallback-review responses remain contract-compliant

---

## Phase 6. Handle no-schema / unmatched path cleanly

- [ ] Identify the exact runtime point where fallback Gemma review should be invoked when schema/manifest is unavailable
- [ ] Ensure unknown-template / provisional flow can still produce review target fields/results
- [ ] Ensure fallback review does not assume schema field names always exist
- [ ] Ensure fallback review remains conservative when context is weak
- [ ] Keep `review_required` semantics valid for unmatched PDFs

---

## Phase 7. Tests

### Unit tests
- [ ] Test matched-template review payload builder
- [ ] Test fallback review payload builder
- [ ] Test Gemma JSON parser with valid structured response
- [ ] Test Gemma JSON parser with malformed response
- [ ] Test merge logic preserves original first-pass `value`
- [ ] Test merge logic preserves original first-pass `confidence`
- [ ] Test unmatched/schema-missing review payload does not crash

### Integration tests
- [ ] Matched PDF with no `review_required` fields -> zero Gemma calls
- [ ] Matched PDF with any `review_required` field -> exactly one Gemma call
- [ ] Many `review_required` fields in one matched PDF -> still exactly one Gemma call
- [ ] Unmatched/schema-missing PDF with any `review_required` field -> exactly one fallback Gemma call
- [ ] Gemma unavailable -> degrade safely without crashing
- [ ] Malformed Gemma response -> degrade safely and preserve conservative status

### Regression tests
- [ ] GLM-OCR per-field extraction still functions
- [ ] Typed field extraction unchanged
- [ ] Checkbox/radio extraction unchanged
- [ ] Existing matched-template success path still works when no Gemma review is triggered

---

## Phase 8. Logging and observability

- [ ] Log whether Gemma review was triggered
- [ ] Log which review mode was used:
  - [ ] matched-template review
  - [ ] fallback review
- [ ] Log reviewed field count
- [ ] Log malformed Gemma response handling
- [ ] Avoid logging sensitive/raw document contents excessively

---

## Phase 9. Cleanup before merge

- [ ] Remove stale per-field Gemma code paths
- [ ] Remove dead helper functions if replaced
- [ ] Remove stale comments/docs inside code
- [ ] Verify plan docs still match implementation
- [ ] Verify README does not describe old per-field Gemma behavior if mentioned there

---

## Acceptance checklist

- [ ] Gemma review is triggered by field-level `review_required`
- [ ] Gemma review runs once per PDF
- [ ] Gemma review works with schema/manifest
- [ ] Gemma review works without schema/manifest
- [ ] First-pass values/confidence are preserved
- [ ] Review output is attached separately
- [ ] Tests cover matched and fallback review modes
- [ ] No remaining code path calls Gemma once per field

---

## Related plan docs

- `IMPLEMENTATION_PLAN_GEMMA_WHOLE_PDF_REVIEW.md`
- `MODEL_ROUTING_DECISION.md`
- `CONFIDENCE_AND_REVIEW_RULES.md`
- `FIELD_RESPONSE_SHAPE_DECISION.md`
- `MATCHED_TEMPLATE_RUNTIME_FLOW.md`
