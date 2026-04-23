# Gemma Whole-PDF Review - Plan Index

This index groups the planning files related to the change from **per-field Gemma review** to **one Gemma review pass per PDF**.

## Core implementation docs

### 1. Main implementation plan
- `IMPLEMENTATION_PLAN_GEMMA_WHOLE_PDF_REVIEW.md`
  - main architecture and rollout plan
  - covers matched-template review + fallback review without schema/manifest

### 2. Coding execution checklist
- `CODING_CHECKLIST_GEMMA_WHOLE_PDF_REVIEW.md`
  - execution-focused checklist for the implementing agent
  - includes code changes, tests, cleanup, and acceptance criteria

---

## Policy / decision docs updated for this change

### 3. Model routing decision
- `MODEL_ROUTING_DECISION.md`
  - GLM stays per field
  - Gemma becomes one-shot per PDF
  - trigger = `any(fr.review_required for fr in field_results)`
  - supports matched-template and fallback review modes

### 4. Confidence and review rules
- `CONFIDENCE_AND_REVIEW_RULES.md`
  - locks field-level `review_required` as the Gemma trigger
  - states review should still work when manifest/schema is missing

### 5. Field response shape
- `FIELD_RESPONSE_SHAPE_DECISION.md`
  - keeps first-pass `value` and `confidence`
  - attaches Gemma output separately in `review`
  - allows `review` to come from matched-template or fallback review

### 6. Matched-template runtime flow
- `MATCHED_TEMPLATE_RUNTIME_FLOW.md`
  - updated runtime flow with one document-level Gemma review pass
  - also notes fallback review when manifest/schema is unavailable

---

## Supporting/stale-doc cleanup updates made

### 7. Top-level response example
- `TOP_LEVEL_RESPONSE_EXAMPLE.md`
  - updated wording for document-level `review_required`

### 8. Analyzer MVP coding checklist
- `ANALYZER_MVP_CODING_CHECKLIST.md`
  - updated wording to match the current field-driven review trigger

### 9. Frozen MVP contract spec
- `FROZEN_MVP_CONTRACT_SPEC.md`
  - adjusted wording around low-confidence review semantics

### 10. Pipeline doc
- `PIPELINE.md`
  - updated stale wording to document-level review language

---

## Recommended reading order for the implementing agent

1. `IMPLEMENTATION_PLAN_GEMMA_WHOLE_PDF_REVIEW.md`
2. `CODING_CHECKLIST_GEMMA_WHOLE_PDF_REVIEW.md`
3. `MODEL_ROUTING_DECISION.md`
4. `CONFIDENCE_AND_REVIEW_RULES.md`
5. `FIELD_RESPONSE_SHAPE_DECISION.md`
6. `MATCHED_TEMPLATE_RUNTIME_FLOW.md`

---

## Scope summary for the agent

The implementing agent should understand these locked rules:

- GLM-OCR remains **per handwritten field**
- Gemma runs **once per PDF**, never once per field
- Gemma trigger = **`any(fr.review_required for fr in field_results)`**
- Gemma review must work:
  - with matched template metadata
  - without matched manifest/schema metadata
- first-pass `value` and `confidence` are preserved
- Gemma review output is attached separately in `review`
