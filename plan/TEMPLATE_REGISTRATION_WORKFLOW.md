# PDF Handwriting Analyzer - Template Registration Workflow

## 1. Purpose

Define how a new blank or canonical PDF form becomes a registered template that the analyzer can later match and use for runtime extraction.

This workflow is the bridge between:
- a new unseen form,
- and a known template in the registry.

---

## 2. Goal

Given a blank or canonical PDF form, the system should be able to:
1. ingest the form,
2. analyze its structure,
3. build template artifacts,
4. register it in the template registry,
5. make it available for future matching and extraction.

---

## 3. Inputs

Preferred input:
- empty / unfilled PDF form

Acceptable fallback input:
- canonical clean PDF version of the form

Not preferred for registration:
- heavily filled forms
- noisy scans
- partially clipped screenshots

Reason:
Template registration should start from the cleanest possible version of the form.

---

## 4. Registration Outputs

A completed registration should produce:
- template manifest
- template schema
- template fingerprint data
- anchor definitions
- optional rendered page assets
- blank PDF stored in template folder

These outputs together make the form usable for:
- template matching
- matched-template runtime extraction

---

## 5. End-to-End Registration Flow

```text
Blank PDF input
  -> validate file
  -> inspect PDF structure
  -> extract fingerprints
  -> detect page geometry and anchors
  -> infer field definitions
  -> build template schema
  -> create template folder and manifest
  -> register template in registry
  -> review and refine if needed
```

---

## 6. Registration Stages

## Stage 1. Validate input template

### Checks
- file exists and is readable
- file is a valid PDF
- page count > 0
- PDF is not obviously corrupted

### Optional checks
- determine whether the document is empty/canonical enough
- inspect whether form is fillable or flattened

### Failure behavior
If the input file is too corrupted or unusable:
- stop registration
- emit clear error

---

## Stage 2. Inspect PDF structure

### Goals
- read metadata
- inspect page count and page sizes
- inspect AcroForm structure if present
- inspect native text anchors if available

### Outputs
- metadata fingerprint
- page signature
- AcroForm fingerprint
- anchor text candidates

This stage creates the first half of the future matching signals.

---

## Stage 3. Detect layout and anchors

### Goals
- identify stable printed text anchors
- identify lines, boxes, sections, and repeated structural cues
- identify likely field regions

### Inputs
- PDF structure
- rendered page images if needed

### Outputs
- anchor definitions
- layout elements
- structural grouping hints

### Note
The anchor set should focus on elements that are stable across filled instances.

---

## Stage 4. Infer field definitions

### Goals
- identify candidate input fields
- attach nearby labels
- classify likely field type
- create initial bboxes

### Possible data sources
- AcroForm fields if available
- widget rectangles
- label-to-box relationships
- detected lines/boxes
- manual review input if needed

### Output
Initial list of template field definitions.

---

## Stage 5. Build template schema

### Goal
Convert detected structure into canonical template schema.

### Schema should include
- page definitions
- section definitions
- field definitions
- anchors
- validation hints
- runtime hints

### Output artifact
- `schema.json`

This is the canonical extraction reference.

---

## Stage 6. Build template manifest

### Goal
Create the registry-facing template record.

### Manifest should include
- identity fields
- fingerprint summaries
- schema references
- runtime hints
- status/version metadata

### Output artifact
- `manifest.json`

This is the canonical matching/lookup reference.

---

## Stage 7. Save assets into template folder

### Recommended template folder structure

```text
templates/
  t2200_fill_25e/
    manifest.json
    schema.json
    anchors.json
    t2200-fill-25e.pdf
    pages/
```

### Saved assets may include
- original blank PDF
- rendered page previews
- anchor files
- optional debug overlays

---

## Stage 8. Register template

### Goal
Make template discoverable by matcher.

### Actions
- add template to top-level registry index if used
- mark template status as `active`, `draft`, or `deprecated`
- validate manifest/schema linkage

### Output
Template becomes loadable by:
- template matcher
- template registry loader
- runtime extraction path

---

## Stage 9. Review and refine

### Why review matters
Automatic inference may not be perfect.
Some forms need adjustment for:
- field bbox accuracy
- field labels
- field types
- runtime hints

### MVP recommendation
Allow light manual review/editing of:
- schema.json
- anchors.json
- manifest.json

This is much more realistic than requiring perfect auto-generation.

---

## 7. Automatic vs Manual Work Split

## Automatic first-pass
The system should try to generate:
- metadata fingerprint
- AcroForm fingerprint
- page geometry
- anchor candidates
- initial field list

## Manual review/refinement
A human may need to confirm or adjust:
- field labels
- ambiguous field types
- bbox corrections
- runtime hints
- template version naming

### Recommendation
Registration should be semi-automatic for MVP, not fully automatic.

---

## 8. T2200 Example Registration Fit

For the T2200 example:
- the empty PDF is a strong registration input
- AcroForm fields are present
- field names like `Last_Name_Fill`, `First_Name_Fill`, and `Tax_Year_Fill` provide strong structure
- page count and title provide additional weak signals

This means T2200 is a very good candidate for early template registration workflow.

Likely registration outputs for T2200:
- `template_id = t2200_fill_25e`
- AcroForm fingerprint with 181 fields
- schema derived from field structure + pages
- anchors derived from title and section headings

---

## 9. Registration Status Model

Suggested statuses:
- `draft` -> generated but not yet reviewed
- `active` -> approved for matching/runtime use
- `deprecated` -> old version, kept for compatibility

### Recommendation
New templates should start as `draft` until minimally reviewed.

---

## 10. Failure Cases

### Bad blank PDF
- unreadable
- corrupted
- weird page structure

### Weak field inference
- labels do not map cleanly
- no clear widget or field geometry

### Unstable anchors
- chosen anchors are likely to be obscured by filled data

### Response
Registration should fail clearly or remain in `draft` until fixed.

---

## 11. MVP Recommendation

For MVP, implement template registration as:
1. ingest clean blank PDF
2. extract AcroForm fingerprint and page signature
3. generate initial schema/manifest
4. save template folder artifacts
5. require light manual review
6. activate template after review

This is practical and safe.

---

## 12. Final Recommendation

The template registration workflow should be semi-automatic and artifact-based.

That gives the analyzer:
- clean known templates,
- stable matching targets,
- and realistic runtime extraction behavior.
