# PDF Handwriting Analyzer - MVP Implementation Decisions

## 1. Purpose

Lock the most important implementation decisions for the analyzer MVP.

These decisions turn open questions into working rules so implementation can start with less ambiguity.

---

## 2. Decision 1 - Analyzer transport style

### Final MVP decision
Use a **local Python service boundary** first.

### Meaning
- Email Manager and analyzer run on the same machine
- Email Manager calls analyzer through local Python integration or an internal service adapter
- keep the JSON request/response contract stable even if the transport is in-process or near in-process

### Why
- simplest implementation
- no need to introduce HTTP/server overhead yet
- easiest to iterate while preserving contract

### Rule
Code should still behave as if analyzer is an external worker behind a contract.
Do not tightly couple Email Manager to analyzer internals.

---

## 3. Decision 2 - Template registry storage format

### Final MVP decision
Use **manifest JSON per template folder**.

### Meaning
Each template gets its own folder, for example:

```text
templates/
  t2200_fill_25e/
    manifest.json
    schema.json
    anchors.json
    t2200-fill-25e.pdf
```

Optional:
- a top-level `registry.json` index later

### Why
- easy to inspect and version in git
- simple enough for MVP
- keeps template assets together

---

## 4. Decision 3 - Template schema authoring method

### Final MVP decision
Use **semi-automatic generation plus manual review**.

### Meaning
- system generates initial fingerprints, fields, anchors, and schema
- human reviews and adjusts manifest/schema if needed
- template becomes `active` only after minimal review

### Why
- realistic for real forms
- safer than pretending first-pass auto-generation is perfect
- faster than full manual authoring from scratch

---

## 5. Decision 4 - Unknown-template runtime policy

### Final MVP decision
Use **fail fast**.

### Meaning
If template matching is not sufficiently confident:
- do not attempt generic extraction
- return structured failure
- set `template_match_status = unknown`

### Why
- safest behavior
- avoids false confidence
- simpler integration with Email Manager

### Rule
Generic unknown-template extraction is out of MVP scope.

---

## 6. Decision 5 - Handwriting extraction strategy

### Final MVP decision
Use **handwriting-capable OCR first, VLM fallback second**.

### Meaning
- primary path for handwritten fields is a specialized handwriting-aware extractor
- VLM or multimodal fallback is used only when handwriting OCR is weak, ambiguous, or suspicious

### Why
- more predictable
- cheaper and simpler for most fields
- keeps fallback targeted instead of defaulting everything to a large model

### Required output rule
For handwritten fields:
- preserve the original field identity
- return interpreted handwritten text in `value`
- attach confidence to that interpreted value

---

## 7. Decision 6 - Artifact retention policy

### Final MVP decision
Persist artifacts **only in debug mode or on failure/review-needed cases**.

### Meaning
Default behavior:
- do not persist every crop and debug file

Persist when:
- analyzer fails
- document is `review_required`
- debug mode is enabled

### Why
- reduces storage noise
- still gives enough debugging visibility when needed

---

## 8. Decision 7 - Encrypted PDF handling

### Final MVP decision
Support **empty-password decrypt** only.

### Meaning
- attempt empty-password decrypt for encrypted PDFs
- if successful, continue
- if not, fail clearly with structured error

### Why
- matches observed T2200 sample behavior
- keeps MVP simple

---

## 9. Decision 8 - Analyzer-side persistence

### Final MVP decision
Keep analyzer **stateless or near-stateless**.

### Meaning
- Email Manager remains the primary owner of jobs and final results
- analyzer may load templates and optionally emit debug artifacts
- analyzer does not need its own heavy runtime results database in MVP

### Why
- simpler architecture
- clearer system boundary
- less duplication of result storage

---

## 10. Summary of Locked MVP Rules

The analyzer MVP will use:
- local Python service boundary
- per-template manifest JSON folders
- semi-automatic template registration with manual review
- fail-fast unknown-template policy
- handwriting OCR first, VLM fallback second
- artifact retention only on failure/review/debug
- empty-password decrypt support for encrypted PDFs
- Email Manager as primary result store

---

## 11. Final Recommendation

These decisions are enough to start implementation without over-designing the first version.

If a later version needs scale or separation, the transport/storage details can evolve while keeping the contract stable.
