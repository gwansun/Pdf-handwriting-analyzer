# PDF Handwriting Analyzer - Template Matching Strategy

## 1. Purpose

Define how the analyzer identifies which template should be used for a given incoming PDF.

Template matching is one of the most important stages in the analyzer because the rest of the extraction pipeline depends on it.

---

## 2. Goal

Given a filled PDF, determine whether it matches:
- a known registered template,
- a weak/provisional template,
- or no known template.

---

## 3. Matching Outcomes

### `matched`
A known template is identified with sufficient confidence.

### `provisional`
A possible template is identified, but confidence is not strong enough for trusted extraction.

### `unknown`
No suitable template is identified.

### MVP recommendation
For MVP, the analyzer should rely mainly on:
- `matched`
- `unknown`

`provisional` can exist in design, but may be deferred.

---

## 4. Matching Signals

Use multiple signals, not only one.

### Signal A. PDF metadata fingerprint
Examples:
- title
- producer
- creator
- subject
- XMP metadata if available

Useful when forms come from stable generation workflows.

### Signal B. AcroForm fingerprint
If the PDF is fillable:
- field names
- field types
- widget rectangles
- field tree structure

This can be a strong signal for form identity.

### Signal C. Page structure signature
Examples:
- page count
- page size(s)
- orientation
- stable label text
- line/box layout hints

### Signal D. Native text anchors
Examples:
- fixed printed labels
- section titles
- repeated headings
- known anchor phrases

### Signal E. Visual anchor signature
For scanned or flattened forms:
- coarse page thumbnail hash
- anchor-region visual match
- known printed label regions

---

## 5. Matching Procedure

### Step 1. Collect candidate fingerprints
From incoming PDF, compute:
- metadata signature
- page signature
- AcroForm signature if present
- anchor text signature
- optional visual fingerprint

### Step 2. Query template registry
Compare incoming signatures to registered templates.

### Step 3. Compute match score
Use weighted comparison across signals.

### Step 4. Choose best template
Return the best candidate if score exceeds threshold.

### Step 5. Apply threshold policy
- high score -> `matched`
- weak score -> `provisional`
- low/no score -> `unknown`

---

## 6. Suggested Initial Scoring Logic

Example weighted approach:

```text
template_match_score =
  0.20 * metadata_score +
  0.30 * acroform_score +
  0.20 * page_structure_score +
  0.20 * anchor_text_score +
  0.10 * visual_anchor_score
```

This is only an MVP baseline.

### Notes
- if AcroForm is present and stable, it may deserve higher weight
- if scanned PDFs dominate, visual + text anchors matter more

---

## 7. Threshold Recommendation

Suggested initial thresholds:
- `>= 0.85` -> `matched`
- `0.65 - 0.84` -> `provisional`
- `< 0.65` -> `unknown`

These should be tuned later using real samples.

---

## 8. Registry Requirements

The template registry should store for each template:
- template id
- version
- metadata fingerprint
- page signature
- AcroForm fingerprint
- anchor texts
- optional visual anchors
- path to template schema

---

## 9. Failure / Edge Cases

### Slightly updated form version
- may resemble existing template strongly
- should not silently match if field geometry drift is large

### Same labels, different geometry
- anchor text alone should not dominate the decision

### Flattened scan without metadata
- rely more on page structure and visual anchors

### Multi-page partial document
- should probably become `unknown` unless partial matching is explicitly supported

---

## 10. MVP Recommendation

For MVP, implement this order of matching:
1. AcroForm fingerprint if available
2. page count and page sizes
3. anchor text signature
4. metadata fingerprint
5. visual anchors only if needed

This keeps the first version practical.

### Practical note from T2200 example
Using the sample files:
- `t2200-fill-25e.pdf` (empty)
- `Gwanjin_t2200-fill-25e_signed.pdf` (filled)

Observed facts:
- both files share weak/generic metadata
- both files are 3 pages
- both files contain AcroForm fields
- both files expose the same field structure
- field names include stable identifiers such as:
  - `Last_Name_Fill`
  - `First_Name_Fill`
  - `Tax_Year_Fill`
  - `Job_Title_Fill`

Conclusion from this example:
- metadata alone is not enough to confidently identify the form as T2200
- AcroForm fingerprint is a strong identification signal
- page count plus AcroForm field names is likely strong enough to identify this template family reliably

This example supports prioritizing AcroForm-based matching before weaker metadata-based matching.

---

## 11. Output Contract Mapping

Template matcher should output:
- `template_match_status`
- `template_id`
- internal match score
- optional reasons / signals used

Only the first two must be exposed in the public response summary.
