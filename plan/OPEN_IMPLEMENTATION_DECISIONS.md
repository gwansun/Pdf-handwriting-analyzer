# PDF Handwriting Analyzer - Open Implementation Decisions

## 1. Purpose

Capture the important analyzer-side decisions that are not fully resolved yet.

The goal is to separate:
- what is already well planned,
- from what still needs a concrete implementation choice.

---

## 2. Decisions Still Open

## Decision 1. Analyzer transport style

### Question
How exactly should Email Manager call the analyzer?

### Options
- direct Python service call
- local HTTP API
- CLI/subprocess invocation

### Recommendation
For MVP, use the simplest local boundary that keeps the JSON contract stable.

### Why still open
The payload shape is defined, but transport/runtime boundary is not fixed.

---

## Decision 2. Template registry storage format

### Question
Should template registry be:
- manifest JSON files in repo,
- one consolidated JSON index,
- or a database-backed registry?

### Recommendation
Manifest JSON per template for MVP.

### Why still open
We recommended it, but it has not been finalized as the implementation rule.

---

## Decision 3. Template schema authoring method

### Question
How are `schema.json` and `anchors.json` created?

### Options
- mostly automatic generation
- semi-automatic generation + manual editing
- fully manual authoring

### Recommendation
Semi-automatic generation with manual review for MVP.

### Why still open
The workflow is planned, but the exact authoring tool/process is not chosen.

---

## Decision 4. Unknown-template handling at runtime

### Question
When no template matches, should analyzer:
- fail fast,
- return review_required,
- or attempt provisional extraction?

### Recommendation
Fail fast for MVP.

### Why still open
This is strongly recommended already, but still an implementation policy choice that should be locked.

---

## Decision 5. Native extraction vs OCR precedence

### Question
When both native text and image-based content exist, what exact precedence rule should be used?

### Recommendation
Use native-first only when trustworthy, otherwise compare or fallback.

### Why still open
The policy direction exists, but the exact trust thresholds are not finalized.

---

## Decision 6. Handwriting extraction engine choice

### Question
What exact engine should handle handwritten field interpretation?

### Possible choices
- OCR-oriented handwriting model
- VLM-based extraction
- hybrid OCR + VLM fallback

### Recommendation
Use a specialized handwriting-capable OCR first, fallback to VLM only when needed.

### Why still open
Architecture is defined, but the concrete engine stack is not locked.

---

## Decision 7. Checkbox and signature implementation detail

### Question
Should checkbox/radio/signature handling be:
- simple rule-based CV,
- OCR-assisted,
- or VLM-assisted?

### Recommendation
Use simple specialized detectors first.

### Why still open
Exact implementation path still depends on tool/library selection.

---

## Decision 8. Confidence weighting and thresholds

### Question
What exact weights and thresholds should be used in MVP?

### Recommendation
Start with current heuristic weights from planning docs and tune later.

### Why still open
The scoring idea exists, but exact constants are not locked against real sample data.

---

## Decision 9. Critical field policy

### Question
Which fields should be considered critical enough to trigger document-level `review_required`?

### Examples
- names
- dates
- employer identity
- signatures
- financial amounts

### Recommendation
Define critical fields per template family.

### Why still open
This is template-specific and not yet encoded in manifests/schema.

---

## Decision 10. Artifact retention policy

### Question
Should analyzer persist temporary artifacts such as:
- cropped field images
- rendered pages
- debug overlays
- alignment outputs?

### Options
- persist nothing by default
- persist on failure only
- persist everything in debug mode

### Recommendation
Persist only in debug mode or on failure for MVP.

### Why still open
Useful for debugging, but storage policy is not finalized.

---

## Decision 11. Encryption and password handling

### Question
How should encrypted PDFs be handled?

### Observed fact
The T2200 samples were encrypted but readable with empty-password decrypt.

### Recommendation
Support empty-password decrypt in MVP, fail clearly otherwise.

### Why still open
This now needs to become a formal runtime rule.

---

## Decision 12. Analyzer-side persistence

### Question
Should analyzer itself persist runtime state/results, or should Email Manager remain the primary result store?

### Recommendation
For MVP, let Email Manager remain the primary result store.
The analyzer can stay stateless or near-stateless.

### Why still open
The current design implies this, but it has not been locked as an explicit architecture decision.

---

## 3. Recommended Decisions To Lock First

If we want to unblock implementation quickly, lock these first:
1. analyzer transport style
2. registry storage format
3. unknown-template runtime policy
4. handwriting extraction engine strategy
5. artifact retention policy

These five choices affect architecture the most.

---

## 4. Final Recommendation

Most of the system is now well planned.
What remains is not broad architecture, but a smaller set of concrete implementation decisions.

That is a good sign.

The next productive step is to explicitly lock the first 3-5 of these decisions and treat them as implementation rules.
