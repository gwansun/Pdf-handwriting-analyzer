# PDF Handwriting Analyzer - Unknown Template Policy

## 1. Purpose

Define what the analyzer should do when an incoming PDF does not clearly match a known template.

This policy matters because bad template assumptions can produce confidently wrong field extraction.

---

## 2. Core Principle

When template certainty is low, the analyzer should be conservative.

It is better to return:
- `unknown`,
- `failed`,
- or `review_required`

than to perform unreliable extraction and pretend the output is trustworthy.

---

## 3. Possible Policies

### Policy A. Fail fast
If template is unknown:
- stop processing
- return structured failure
- ask caller to register template or retry later

### Policy B. Provisional generic extraction
If template is unknown:
- attempt generic layout analysis
- produce lower-confidence output
- mark strong review requirement

### Policy C. Hybrid policy
- fail fast for unsupported document classes
- allow provisional extraction only for limited supported cases

---

## 4. MVP Recommendation

Use **Policy A: Fail fast** for MVP.

Reason:
- simpler implementation
- safer output
- cleaner integration with Email Manager
- avoids false confidence early on

---

## 5. Recommended Failure Response

If template is unknown, return a structured response such as:

```json
{
  "request_id": "req_123",
  "job_id": "job_123",
  "status": "failed",
  "summary": {
    "template_match_status": "unknown",
    "template_id": null,
    "page_count": 2,
    "overall_confidence": 0.0,
    "review_required": true,
    "warning_count": 1,
    "field_count": 0
  },
  "warnings": [
    {
      "code": "UNKNOWN_TEMPLATE",
      "message": "No matching registered template was found"
    }
  ],
  "error": {
    "code": "UNKNOWN_TEMPLATE",
    "message": "Template matching failed for this PDF",
    "retryable": false
  }
}
```

---

## 6. When Provisional Extraction Might Be Allowed Later

Later versions may allow provisional extraction if:
- page structure strongly resembles a known family of forms
- field geometry can be inferred safely
- extraction is marked review-required by default
- downstream consumers understand confidence is weak

---

## 7. Email Manager Integration Impact

Email Manager should interpret unknown-template output as:
- analysis failed safely
- job may need manual review or later template registration
- no field-level extraction should be trusted

This keeps system behavior honest.

---

## 8. Recommendation

For now:
- known template -> analyze
- unknown template -> fail with structured error

Do not add generic extraction until enough samples exist to validate it.
