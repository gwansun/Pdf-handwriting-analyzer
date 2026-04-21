# Frozen MVP Spec Index

This file is the main entry point for the PDF analyzer MVP specification.

It points to the documents that define the locked MVP behavior for implementation.

---

## 1. Core contract
- `FROZEN_MVP_CONTRACT_SPEC.md`
  - frozen request/response contract for MVP
- `EMAIL_MANAGER_CONTRACT_ALIGNMENT.md`
  - alignment notes with Email Manager integration

## 2. Model routing and review behavior
- `MODEL_ROUTING_DECISION.md`
  - GLM-OCR as primary handwritten extraction on `http://127.0.0.1:11436`
  - Gemma4 e4b as review/refine model on `http://127.0.0.1:11435`
  - review trigger at confidence `< 0.70`
- `CONFIDENCE_AND_REVIEW_RULES.md`
  - low-confidence handling
  - document-level `review_required` rule
  - confidence remains the original GLM-OCR confidence

## 3. Field and response shape
- `FIELD_RESPONSE_SHAPE_DECISION.md`
  - field-level shape for handwritten response values
  - `value`, `confidence`, `review`, `warnings`
- `TOP_LEVEL_RESPONSE_EXAMPLE.md`
  - concrete examples for `completed`, `review_required`, and `failed`

## 4. Template system
- `TEMPLATE_REGISTRY_DESIGN.md`
  - manifest-per-template registry structure
- `MINIMUM_MANIFEST_SCHEMA.md`
  - minimum manifest structure
- `MINIMUM_SCHEMA_FIELD_FORMAT.md`
  - field schema format
- `TEMPLATE_MATCHING_STRATEGY.md`
  - template identification strategy
- `UNKNOWN_TEMPLATE_POLICY.md`
  - fail-fast policy for unknown templates
- `TEMPLATE_REGISTRATION_WORKFLOW.md`
  - how new templates are added
- `MATCHED_TEMPLATE_RUNTIME_FLOW.md`
  - runtime flow after a template is matched

## 5. Extraction behavior
- `FIELD_EXTRACTION_POLICY.md`
  - handling rules by field type

## 6. Locked implementation decisions
- `MVP_IMPLEMENTATION_DECISIONS.md`
  - main frozen MVP choices

---

## Supporting context docs
These are useful, but not the first source of truth for locked MVP behavior:

- `ANALYZER_INTEGRATION_MASTER_PLAN.md`
- `ANALYZER_INTERNAL_TASK_BREAKDOWN.md`
- `ARCHITECTURE.md`
- `PIPELINE.md`
- `CONFIDENCE_SCORING.md`
- `RESPONSE_EXAMPLES.md`
- `TEMPLATE_SCHEMA.md`
- `OPEN_IMPLEMENTATION_DECISIONS.md`

---

## Recommended reading order for implementation
1. `FROZEN_MVP_SPEC_INDEX.md`
2. `FROZEN_MVP_CONTRACT_SPEC.md`
3. `MODEL_ROUTING_DECISION.md`
4. `CONFIDENCE_AND_REVIEW_RULES.md`
5. `FIELD_RESPONSE_SHAPE_DECISION.md`
6. `TOP_LEVEL_RESPONSE_EXAMPLE.md`
7. `TEMPLATE_REGISTRY_DESIGN.md`
8. `MINIMUM_MANIFEST_SCHEMA.md`
9. `MINIMUM_SCHEMA_FIELD_FORMAT.md`
10. `TEMPLATE_MATCHING_STRATEGY.md`
11. `FIELD_EXTRACTION_POLICY.md`
12. `MVP_IMPLEMENTATION_DECISIONS.md`

---

## Purpose
The goal of this index is to prevent implementation drift by making the frozen MVP decisions easy to find and follow.
