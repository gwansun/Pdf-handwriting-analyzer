# Short Handoff Note - Gemma Whole-PDF Implementation (2026-04-22)

## Status
Not accepted yet.

## Main blockers to fix

1. **Fix broken fallback call sites in `main.py`**
   - `extract_unknown_filled_pdf(...)` is called with the wrong arguments
   - current calls pass `glm_available=...`, but the function expects:
     - `pdf_path`
     - `inspection`
     - `request_id`
     - `job_id`
     - optional `registry`

2. **Implement fallback/no-schema Gemma review path**
   - matched-template Gemma review exists
   - fallback/no-schema Gemma review is still not wired into runtime
   - requirement is: Gemma whole-document review must work both with and without manifest/schema metadata

3. **Fix average confidence lookup in `src/extractors/gemma_client.py`**
   - payload builders store confidence under:
     - `payload["document"]["average_document_confidence"]`
   - prompt builders currently read from:
     - `payload.get("average_document_confidence", 0.0)`
   - update prompt builders to read the actual payload shape

4. **Fix `_extract_handwritten(...)` signature mismatch in `field_router.py`**
   - caller/callee do not match
   - remove any leftover `gemma_available` dependency from field routing if Gemma is document-level only

5. **Resolve final `review_required` semantics in `main.py`**
   - current scorer uses average document confidence trigger
   - but final code still does:
     - `review_required = review_required or any(fr.review_required for fr in field_results)`
   - decide whether field-level flags are informational only or still affect final document status

6. **Remove leftover debug prints**
   - remove `DEBUG ...` stderr output from `field_router.py`

## Tests required

- matched PDF, avg confidence `< 0.70` → exactly one Gemma call
- matched PDF, avg confidence `>= 0.70` → zero Gemma calls
- many weak fields in one PDF → still one Gemma call
- fallback/no-schema PDF, low average confidence → one fallback Gemma call
- Gemma unavailable → safe degradation
- malformed Gemma response → safe degradation
- first-pass `value` and `confidence` stay unchanged after review merge

## Acceptance target
Approve only after:
- fallback lane runs without signature/argument errors
- fallback Gemma review is truly implemented
- Gemma uses correct average confidence
- no per-field Gemma call remains
- one PDF triggers at most one Gemma call
- tests cover matched + fallback whole-document review paths
