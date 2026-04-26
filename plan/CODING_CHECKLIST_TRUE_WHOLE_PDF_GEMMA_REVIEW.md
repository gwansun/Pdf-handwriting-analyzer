# Coding Checklist — True Whole-PDF Gemma Review

## Confirmed decisions

1. **Trigger rule**
   - If **any single field** is below the confidence threshold, trigger Gemma review.

2. **Review scope**
   - For matched-template documents, Gemma should review **relevant pages only**.
   - Relevant pages are derived from the low-confidence target fields' schema page numbers.

3. **Failure behavior**
   - If multimodal Gemma whole-PDF review fails, do **not** fall back to text-only review.
   - Instead, show a **clear user-visible issue message** in the same UI area where Gemma feedback would normally appear.

---

## Goal

Upgrade the current Gemma second-pass review so that Gemma reviews the **actual PDF page images** for the relevant pages, instead of only reviewing OCR/text outputs.

The result should still attach structured per-field review feedback back onto the extracted field list for Email Manager.

---

## Desired behavior

### Trigger
- Run Gemma whole-PDF review when `any(field.review_required)` is true.
- Gemma must still be called **once per PDF**, not once per field.

### Input to Gemma
Gemma should receive:
- rendered page images for the relevant PDF pages
- template/schema metadata
- first-pass OCR results
- low-confidence target field list
- optional supporting context from nearby schema fields if useful

### Output from Gemma
Preserve current response shape:

```json
{
  "reviewed_fields": [
    {
      "field_name": "...",
      "reviewed_value": "...",
      "reviewed_confidence": 0.82,
      "reasoning": "..."
    }
  ],
  "document_notes": ["..."]
}
```

### Failure UX
If Gemma whole-PDF review fails:
- do not silently drop the issue
- do not use text-only fallback review
- attach a field-level or document-level message that the UI can display clearly, e.g.
  - `Gemma whole-document review was unavailable.`
  - `Gemma could not review the relevant PDF pages.`
  - include concise reason if safe and useful

---

## Phase 1 — multimodal feasibility and contract

### 1.1 Confirm Gemma endpoint supports multimodal page-image input
- [ ] Verify the serving endpoint accepts `messages[].content[]` with mixed text and `image_url`
- [ ] Confirm multiple page images can be sent in one request
- [ ] Confirm practical page/image limits
- [ ] Confirm timeout expectations for 1-5 page review requests

### 1.2 Define request contract for Gemma whole-PDF review
- [ ] Extend review request model to support page images
- [ ] Decide canonical image payload format
  - likely base64 `data:image/png;base64,...`
- [ ] Keep existing structured JSON response contract unchanged

### 1.3 Define failure contract
- [ ] Add explicit review-failure reporting structure for analyzer output
- [ ] Decide whether failure is represented by:
  - field warnings
  - field `review_comment`
  - top-level warnings
  - or a dedicated `review_status` / `review_error` field
- [ ] Recommendation: keep backward compatibility by using field/top-level warnings first, add new field only if necessary

---

## Phase 2 — page rendering helper

### 2.1 Add dedicated page-rendering helper module
Suggested new module:
- `src/extractors/gemma_review_pages.py`

### 2.2 Implement rendering functionality
- [ ] Render PDF pages to images for Gemma review
- [ ] Support page-number subset rendering
- [ ] Normalize image format and size
- [ ] Add resizing/compression policy for stable payload size

### 2.3 Add safeguards
- [ ] Handle missing/unreadable PDF
- [ ] Handle encrypted PDFs
- [ ] Handle oversized docs or too many target pages
- [ ] Return structured failure reason to caller

---

## Phase 3 — relevant-page selection

### 3.1 Matched-template page selection
- [ ] Collect low-confidence target field names
- [ ] Map target fields to schema page numbers
- [ ] Build de-duplicated relevant page list
- [ ] Preserve stable order

### 3.2 Optional context enrichment
- [ ] Consider whether to include additional same-page non-target schema fields as prompt context
- [ ] Consider whether to include neighboring pages only if target fields span ambiguous page boundaries
- [ ] Recommendation: initial MVP = only exact relevant pages

### 3.3 Caps and limits
- [ ] Add max relevant page cap
- [ ] Define behavior when cap exceeded
  - truncate with warning
  - or fail review with visible issue
- [ ] Recommendation: truncate with explicit warning surfaced to UI

---

## Phase 4 — Gemma client multimodal upgrade

### 4.1 Extend `review_document_extraction(...)`
- [ ] Add support for rendered page images input
- [ ] Keep existing text-only arguments for schema/results/targets

### 4.2 Update request payload builder
- [ ] For matched-template review, include:
  - relevant page images
  - template metadata
  - schema fields
  - first-pass results
  - target fields

### 4.3 Update prompt design
- [ ] Explicitly tell Gemma it is reviewing the **actual PDF pages**
- [ ] Tell Gemma to use page images as primary evidence
- [ ] Tell Gemma to use OCR output as supporting context, not the only source of truth
- [ ] Require per-target reasoning

### 4.4 Failure handling
- [ ] If multimodal request fails, return structured “review unavailable” result
- [ ] Do **not** perform text-only fallback

---

## Phase 5 — analyzer integration in matched-template path

### 5.1 Update trigger path in `main.py`
- [ ] Keep trigger condition: `any(fr.review_required for fr in field_results)`
- [ ] Identify review target fields
- [ ] Resolve relevant pages from schema
- [ ] Render relevant pages
- [ ] Invoke Gemma multimodal whole-PDF review once

### 5.2 Merge review result back into field results
- [ ] Continue setting:
  - `review`
  - `review_comment`
- [ ] Preserve original first-pass OCR value/confidence
- [ ] Only annotate target fields returned by Gemma

### 5.3 Surface review failure state
- [ ] If Gemma whole-PDF review fails, attach visible user-facing message
- [ ] Ensure failure message lands in output consumed by Email Manager
- [ ] Ensure message appears where feedback is displayed in frontend

---

## Phase 6 — fallback/unknown-template path

### 6.1 Keep scope limited initially
- [ ] Do **not** expand fallback path until matched-template multimodal review is stable

### 6.2 Fallback plan after matched-template success
- [ ] Add capped page rendering for fallback documents
- [ ] Select pages conservatively
- [ ] Reuse same failure UX rule: no text-only fallback, visible issue message instead

---

## Phase 7 — backend/API compatibility

### 7.1 Analyzer adapter
- [ ] Confirm Email Manager adapter preserves review output fields unchanged
- [ ] Extend adapter only if new review-failure fields are added

### 7.2 Persistence
- [ ] Ensure review comments and any failure messages survive DB persistence
- [ ] If needed, augment stored field/top-level result mapping

### 7.3 API response shaping
- [ ] Ensure email detail endpoint returns:
  - Gemma review comments
  - Gemma review unavailable/failure message when applicable

---

## Phase 8 — frontend behavior

### 8.1 Review display block
- [ ] Keep current Gemma review block for successful review comments
- [ ] Add clear failure display state for review-unavailable cases

### 8.2 Failure message UX
- [ ] Show explicit message where Gemma feedback normally appears
- [ ] Distinguish between:
  - review succeeded with comment
  - review unavailable / failed
- [ ] Avoid silent absence of review text for low-confidence fields

### 8.3 Suggested UI copy
Examples:
- `Gemma whole-document review unavailable.`
- `Gemma could not review the relevant PDF pages.`
- `Review failed: timeout while analyzing relevant pages.`

---

## Phase 9 — tests

### 9.1 Analyzer unit tests
- [ ] Test page selection from low-confidence target fields
- [ ] Test PDF page rendering helper
- [ ] Test multimodal request construction includes page images
- [ ] Test trigger when any single field is below threshold
- [ ] Test one-call-per-PDF invariant
- [ ] Test successful merge of reviewed fields
- [ ] Test review failure returns visible issue message
- [ ] Test no text-only fallback occurs on multimodal failure

### 9.2 Analyzer integration tests
- [ ] Verify matched-template flow sends actual page images to Gemma
- [ ] Verify target review comments come back on low-confidence fields
- [ ] Verify failure case surfaces review-unavailable message in analyzer output

### 9.3 Email Manager backend tests
- [ ] Verify adapter persists review failure message correctly
- [ ] Verify email detail API returns review failure message for affected fields/attachment

### 9.4 Frontend E2E tests
- [ ] Add E2E for successful Gemma whole-PDF feedback display
- [ ] Add E2E for Gemma review failure message display
- [ ] Keep existing email detail review UI tests passing

---

## Phase 10 — frozen binary + runtime validation

### 10.1 Binary rebuild
- [ ] Rebuild PyInstaller binary after implementation
- [ ] Confirm new multimodal code is included

### 10.2 Parity validation
- [ ] Compare source-path and frozen-binary behavior on the same document
- [ ] Verify both produce the same review/failure semantics

### 10.3 Live Email Manager validation
- [ ] Point Email Manager to rebuilt binary
- [ ] Retry a real low-confidence PDF job
- [ ] Confirm live UI shows either:
  - Gemma review comment(s), or
  - clear Gemma review failure message

---

## Suggested implementation order

1. **Multimodal feasibility check**
2. **Page-rendering helper**
3. **Relevant-page selection**
4. **Matched-template multimodal Gemma integration**
5. **Failure-message surfacing**
6. **Analyzer tests**
7. **Email Manager API/UI verification**
8. **Binary rebuild + parity check**
9. **Fallback-path extension later**

---

## Handoff notes for sub-agent

### Key non-negotiables
- Trigger Gemma when **any field** is below threshold
- Review **relevant PDF pages only** for matched-template docs
- **No text-only fallback review** if multimodal whole-PDF review fails
- Failure must be **visible to the user** where review feedback is displayed
- Keep one Gemma call per PDF
- Preserve first-pass OCR values separately from Gemma review output

### Recommended first implementation target
- matched-template path only
- leave fallback path for second pass after matched-template path is stable
