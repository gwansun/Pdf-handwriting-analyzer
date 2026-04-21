# PDF Handwriting Analyzer - Response Examples

## 1. Purpose

Provide concrete JSON response examples for the analyzer.

These examples make the integration contract easier to implement and test for both:
- PDF analyzer
- Email Manager

The examples follow the shared contract where:
- field structure is preserved
- handwritten fields return interpreted text values
- confidence is attached to the interpreted value

---

## 2. Example A - Completed

Use when:
- template match is strong
- extraction is usable
- no major review warning is needed

```json
{
  "request_id": "req_001",
  "job_id": "job_001",
  "status": "completed",
  "summary": {
    "template_match_status": "matched",
    "template_id": "t2200_fill_25e",
    "page_count": 3,
    "overall_confidence": 0.91,
    "review_required": false,
    "warning_count": 0,
    "field_count": 4
  },
  "fields": [
    {
      "field_name": "employee_last_name",
      "field_label": "Last name",
      "field_type": "handwritten_name",
      "value": "Romero",
      "confidence": 0.93,
      "validation_status": "valid",
      "review_required": false,
      "warnings": [],
      "bbox": [210, 320, 520, 395],
      "confidence_breakdown": {
        "extractor_confidence": 0.92,
        "image_quality_score": 0.95,
        "alignment_score": 0.96,
        "pattern_validation_score": 0.88
      }
    },
    {
      "field_name": "employee_first_name",
      "field_label": "First name",
      "field_type": "handwritten_name",
      "value": "Leonardo",
      "confidence": 0.90,
      "validation_status": "valid",
      "review_required": false,
      "warnings": [],
      "bbox": [540, 320, 880, 395]
    },
    {
      "field_name": "tax_year",
      "field_label": "Tax year",
      "field_type": "number",
      "value": "2025",
      "confidence": 0.98,
      "validation_status": "valid",
      "review_required": false,
      "warnings": [],
      "bbox": [900, 320, 1010, 395]
    },
    {
      "field_name": "employer_name",
      "field_label": "Employer name",
      "field_type": "text",
      "value": "ABC Manufacturing Inc.",
      "confidence": 0.95,
      "validation_status": "valid",
      "review_required": false,
      "warnings": [],
      "bbox": [220, 470, 900, 550]
    }
  ],
  "warnings": [],
  "raw_result": {
    "analyzer_version": "0.1.0",
    "timing_ms": 1680
  }
}
```

---

## 3. Example B - Review Required

Use when:
- extraction succeeded,
- but one or more fields are ambiguous or weak,
- especially handwritten fields with lower confidence.

```json
{
  "request_id": "req_002",
  "job_id": "job_002",
  "status": "review_required",
  "summary": {
    "template_match_status": "matched",
    "template_id": "t2200_fill_25e",
    "page_count": 3,
    "overall_confidence": 0.72,
    "review_required": true,
    "warning_count": 2,
    "field_count": 3
  },
  "fields": [
    {
      "field_name": "employee_first_name",
      "field_label": "First name",
      "field_type": "handwritten_name",
      "value": "Leonardo",
      "confidence": 0.89,
      "validation_status": "valid",
      "review_required": false,
      "warnings": [],
      "bbox": [540, 320, 880, 395]
    },
    {
      "field_name": "employee_last_name",
      "field_label": "Last name",
      "field_type": "handwritten_name",
      "value": "Romera",
      "confidence": 0.61,
      "validation_status": "uncertain",
      "review_required": true,
      "warnings": [
        "ambiguous_handwriting"
      ],
      "bbox": [210, 320, 520, 395],
      "candidates": [
        {
          "value": "Romera",
          "confidence": 0.61
        },
        {
          "value": "Romero",
          "confidence": 0.57
        }
      ],
      "confidence_breakdown": {
        "extractor_confidence": 0.58,
        "image_quality_score": 0.74,
        "alignment_score": 0.95,
        "pattern_validation_score": 0.60
      }
    },
    {
      "field_name": "employee_signature_name",
      "field_label": "Employee signature",
      "field_type": "handwritten_name",
      "value": "Leonardo Romero",
      "confidence": 0.67,
      "validation_status": "uncertain",
      "review_required": true,
      "warnings": [
        "signature_style_handwriting",
        "manual_review_recommended"
      ],
      "bbox": [300, 2200, 1120, 2400]
    }
  ],
  "warnings": [
    {
      "code": "LOW_CONFIDENCE_HANDWRITING",
      "message": "One or more handwritten fields are ambiguous"
    },
    {
      "code": "MANUAL_REVIEW_RECOMMENDED",
      "message": "Please verify low-confidence handwritten fields"
    }
  ],
  "raw_result": {
    "analyzer_version": "0.1.0",
    "timing_ms": 2140
  }
}
```

---

## 4. Example C - Failed / Unknown Template

Use when:
- no known template can be matched safely,
- analyzer chooses conservative failure.

```json
{
  "request_id": "req_003",
  "job_id": "job_003",
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
  "fields": [],
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
  },
  "raw_result": {
    "analyzer_version": "0.1.0",
    "timing_ms": 490
  }
}
```

---

## 5. Example D - Failed / File Problem

Use when:
- request is valid,
- but PDF file cannot be read or found.

```json
{
  "request_id": "req_004",
  "job_id": "job_004",
  "status": "failed",
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "PDF file does not exist at provided file.path",
    "retryable": true
  },
  "raw_result": {
    "analyzer_version": "0.1.0",
    "timing_ms": 15
  }
}
```

---

## 6. Key Rules Reinforced By These Examples

### Rule 1
Preserve the original field structure.

### Rule 2
For handwritten fields, return interpreted handwritten text in `value`.

### Rule 3
Attach confidence to that interpreted value.

### Rule 4
Use `review_required` when extraction is usable but uncertain.

### Rule 5
Fail conservatively when the template is unknown or file input is invalid.

---

## 7. Final Recommendation

Use these examples as contract fixtures for both systems.

They are useful for:
- backend integration tests
- analyzer response validation
- frontend dashboard mock data
