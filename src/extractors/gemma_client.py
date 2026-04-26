"""
Gemma 4 review/refine client — document-level.

Endpoint: http://127.0.0.1:11435

Called once per PDF when average document confidence < 0.70.
Supports two modes:
  - matched_template_review: template manifest + schema are available
  - fallback_review: no template metadata; use available document signals

Returns structured JSON from Gemma (not free-form TEXT:/CONFIDENCE:/REASONING:).
"""
import httpx
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from common.config import GEMMA_ENDPOINT, MODEL_TIMEOUT_SECONDS

logger = logging.getLogger("gemma_client")


def _candidate_gemma_endpoints() -> list[str]:
    # 11436 (mlx-vlm) is primary — it serves Gemma via /v1/chat/completions correctly.
    # 11435 (mlx_lm) only supports /v1/completions, not /v1/chat/completions.
    from common.config import GLM_OCR_ENDPOINT, GEMMA_ENDPOINT
    return [GLM_OCR_ENDPOINT, GEMMA_ENDPOINT]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def review_document_extraction(
    review_mode: str,
    gemma_available: bool,
    # Matched-template context
    template: Optional[dict] = None,
    schema_fields: Optional[list[dict]] = None,
    first_pass_results: Optional[list[dict]] = None,
    # Fallback context
    document: Optional[dict] = None,
    inspection: Optional[dict] = None,
    provisional_results: Optional[list[dict]] = None,
    warnings: Optional[list[str]] = None,
    page_images: Optional[list[dict]] = None,
    field_images: Optional[list[dict]] = None,
    # Trigger inputs
    average_document_confidence: float = 0.0,
    review_target_fields: Optional[list[str]] = None,
) -> "GemmaReviewResult":
    """
    Invoke Gemma once for the whole PDF to review first-pass extraction results.
    """
    if not gemma_available:
        logger.warning("Gemma unavailable — skipping document review")
        return GemmaReviewResult(
            reviewed_fields=[],
            document_notes=[],
            error_message="Gemma whole-document review is unavailable.",
        )

    if review_mode == "matched_template_review":
        payload = _build_matched_template_payload(
            template=template,
            schema_fields=schema_fields,
            first_pass_results=first_pass_results,
            page_images=page_images,
            field_images=field_images,
            average_document_confidence=average_document_confidence,
            review_target_fields=review_target_fields,
        )
    elif review_mode == "fallback_review":
        payload = _build_fallback_payload(
            document=document,
            inspection=inspection,
            provisional_results=provisional_results,
            page_images=page_images,
            field_images=field_images,
            average_document_confidence=average_document_confidence,
            review_target_fields=review_target_fields,
            warnings=warnings,
        )
    else:
        logger.error(f"Unknown review_mode: {review_mode}")
        return GemmaReviewResult(reviewed_fields=[], document_notes=[])

    return _call_gemma(payload)


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

def _build_matched_template_payload(
    template: dict,
    schema_fields: list[dict],
    first_pass_results: list[dict],
    page_images: Optional[list[dict]],
    field_images: Optional[list[dict]],
    average_document_confidence: float,
    review_target_fields: Optional[list[str]],
) -> dict:
    return {
        "review_mode": "matched_template_review",
        "template": template,
        "document": {
            "average_document_confidence": average_document_confidence,
        },
        "schema_fields": schema_fields,
        "first_pass_results": first_pass_results,
        "page_images": page_images or [],
        "field_images": field_images or [],
        "review_target_fields": review_target_fields or [],
    }


def _build_fallback_payload(
    document: dict,
    inspection: dict,
    provisional_results: list[dict],
    page_images: Optional[list[dict]],
    field_images: Optional[list[dict]],
    average_document_confidence: float,
    review_target_fields: Optional[list[str]],
    warnings: Optional[list[str]],
) -> dict:
    return {
        "review_mode": "fallback_review",
        "document": {
            "page_count": document.get("page_count", 0) if document else 0,
            "average_document_confidence": average_document_confidence,
            "metadata": document.get("metadata", {}) if document else {},
        },
        "inspection": inspection or {},
        "provisional_results": provisional_results or [],
        "page_images": page_images or [],
        "field_images": field_images or [],
        "review_target_fields": review_target_fields or [],
        "warnings": warnings or [],
    }


# ---------------------------------------------------------------------------
# Gemma API call
# ---------------------------------------------------------------------------

def _call_gemma(payload: dict) -> "GemmaReviewResult":
    """
    Send a structured JSON payload to Gemma and parse the structured response.

    Returns GemmaReviewResult. On any failure, degrades gracefully and returns
    an empty result so the pipeline can continue.
    """
    prompt = _build_prompt(payload)

    request_payload = {
        "model": "mlx-community/gemma-4-e4b-it-4bit",
        "messages": [_build_message(prompt, payload)],
        "max_tokens": 8192,
        "temperature": 0.1,
    }

    try:
        with httpx.Client(timeout=MODEL_TIMEOUT_SECONDS) as client:
            last_exc = None
            for endpoint in _candidate_gemma_endpoints():
                try:
                    resp = client.post(
                        f"{endpoint}/v1/chat/completions",
                        json=request_payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    logger.info(f"Gemma raw response from {endpoint}: {content[:300]!r}")
                    try:
                        with open("/tmp/gemma_raw_response.txt", "w") as f:
                            f.write(content)
                    except Exception:
                        pass
                    return _parse_gemma_response(content)
                except Exception as exc:
                    last_exc = exc
                    continue

    except Exception as exc:
        last_exc = exc

    logger.warning(f"Gemma review call failed: {last_exc}")
    return GemmaReviewResult(
        reviewed_fields=[],
        document_notes=[],
        error_message="Gemma whole-document review could not review the relevant PDF pages.",
    )


def _build_message(prompt: str, payload: dict) -> dict:
    page_images = payload.get("page_images", []) or []
    field_images = payload.get("field_images", []) or []
    if not page_images and not field_images:
        return {"role": "user", "content": prompt}

    content = [{"type": "text", "text": prompt}]
    for field_image in field_images:
        image_url = field_image.get("image_url")
        if not image_url:
            continue
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            }
        )
    for page in page_images:
        image_url = page.get("image_url")
        if not image_url:
            continue
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            }
        )

    return {"role": "user", "content": content}


def _build_prompt(payload: dict) -> str:
    """
    Convert the structured payload into a clear text prompt for Gemma.
    Gemma is asked to respond with strict JSON.
    """
    review_mode = payload.get("review_mode", "unknown")

    if review_mode == "matched_template_review":
        return _matched_template_prompt(payload)
    elif review_mode == "fallback_review":
        return _fallback_prompt(payload)
    else:
        return "Review the following extraction results and return valid JSON."


def _matched_template_prompt(payload: dict) -> str:
    template = payload.get("template", {})
    schema_fields = payload.get("schema_fields", [])
    first_pass = payload.get("first_pass_results", [])
    page_images = payload.get("page_images", [])
    field_images = payload.get("field_images", [])
    avg_conf = payload.get("document", {}).get("average_document_confidence", 0.0)
    targets = payload.get("review_target_fields", [])

    schema_block = json.dumps(schema_fields, indent=2)
    first_pass_block = json.dumps(first_pass, indent=2)
    targets_list = ", ".join(targets) if targets else "all low-confidence fields"
    page_descriptions = "\n".join(
        f"- Page {page.get('page_number', '?')} ({page.get('width', '?')}x{page.get('height', '?')})"
        for page in page_images
    ) or "- No rendered pages attached"
    field_crop_descriptions = "\n".join(
        f"- Crop for {img.get('field_name', '?')} / {img.get('field_label', '?')} on page {img.get('page_number', '?')} ({img.get('width', '?')}x{img.get('height', '?')})"
        for img in field_images
    ) or "- No field crops attached"

    return f"""You are reviewing handwritten text extractions from a government form.

Document info:
- Template: {template.get('display_name', 'Unknown')} ({template.get('template_id', '')})
- Average document confidence: {avg_conf:.2f}
- Attached PDF page images for review:
{page_descriptions}
- Attached field crops for focused review:
{field_crop_descriptions}

Your task:
Review the first-pass extraction results below against the attached PDF page images and field crops. Use the field crops as primary evidence when they are attached for a target field, and use the full rendered PDF pages for surrounding context. For each field in {targets_list}, compare the document content against the extracted value. Correct any obvious OCR errors, normalize formatting where appropriate (e.g. names, dates, SINs), and flag truly unreadable fields.

**Conflict resolution:** If a field crop and the full page disagree on what is written, TRUST THE CROP — the crop is a closer, higher-resolution view. Only use the full page to resolve ambiguity in the crop.

**Confidence scale:** reviewed_confidence is a float from 0.0 (completely unreadable) to 1.0 (fully confident). If you are uncertain about a correction, keep reviewed_confidence below 0.80.

**Coverage rule:** You MUST include every target field in reviewed_fields. If a field is unreadable in BOTH the attached crop AND the full page image, keep the first-pass value (or empty string if none), assign low confidence, and flag it as unreadable.

**Evidence rule:** Never infer missing characters from context alone unless the image evidence strongly supports it.

Return a JSON object with this exact shape:
{{
  "reviewed_fields": [
    {{
      "field_name": "<field_name>",
      "reviewed_value": "<your corrected or confirmed value>",
      "reviewed_confidence": <0.0 to 1.0, required>,
      "reasoning": "<brief explanation, required for each field>",
      "flagged_issues": ["unreadable", "crop_page_conflict", "format_normalized", "low_confidence", "possible_ocr_error"]
    }}
  ],
  "document_notes": {{
    "readability_notes": "<optional overall note>",
    "flagged_issues": ["unreadable", "crop_page_conflict", "format_normalized", "low_confidence", "possible_ocr_error"]
  }}
}}

Rules:
- You MUST include every target field in reviewed_fields
- For each target field, always provide a non-empty reasoning string
- If you agree with the first-pass value, repeat it in reviewed_value and explain why
- If a field is unreadable in both crop and full page, keep the first-pass value (or empty string if none), assign low confidence, and include "unreadable" in flagged_issues
- If attached field crops exist for a target field, inspect those crops before declaring the field unreadable
- If the attached images do not show enough evidence, say so clearly in reasoning instead of guessing
- Never infer missing characters from context alone unless the image evidence strongly supports it
- reviewed_confidence MUST be between 0.0 and 1.0; if uncertain, keep it below 0.80
- Use only these flagged_issues values when relevant: unreadable, crop_page_conflict, format_normalized, low_confidence, possible_ocr_error
- Return valid JSON only — no extra text

Schema fields ({len(schema_fields)} total):
{schema_block}

First-pass extraction results:
{first_pass_block}
"""


def _fallback_prompt(payload: dict) -> str:
    doc = payload.get("document", {})
    insp = payload.get("inspection", {})
    prov = payload.get("provisional_results", [])
    page_images = payload.get("page_images", [])
    field_images = payload.get("field_images", [])
    avg_conf = doc.get("average_document_confidence", 0.0)
    targets = payload.get("review_target_fields", [])
    warnings = payload.get("warnings", [])

    prov_block = json.dumps(prov, indent=2) if prov else "[]"
    warnings_block = "\n".join(f"- {w}" for w in warnings) if warnings else "None"
    targets_list = ", ".join(targets) if targets else "all low-confidence provisional fields"
    page_descriptions = "\n".join(
        f"- Page {page.get('page_number', '?')} ({page.get('width', '?')}x{page.get('height', '?')})"
        for page in page_images
    ) or "- No rendered pages attached"
    field_crop_descriptions = "\n".join(
        f"- Crop for {img.get('field_name', '?')} / {img.get('field_label', '?')} on page {img.get('page_number', '?')} ({img.get('width', '?')}x{img.get('height', '?')})"
        for img in field_images
    ) or "- No field crops attached"

    return f"""You are reviewing text extractions from a PDF document where no template metadata is available.

Document info:
- Page count: {doc.get('page_count', 'unknown')}
- Average document confidence: {avg_conf:.2f}
- Classification: born_digital={insp.get('is_born_digital')}, scanned={insp.get('is_scanned')}, hybrid={insp.get('is_hybrid')}
- AcroForm fields: {insp.get('acroform_field_names', [])}
- Warnings: {warnings_block}
- Attached PDF page images for review:
{page_descriptions}
- Attached field crops for focused review:
{field_crop_descriptions}

Your task:
Review the provisional extraction results against the attached PDF page images and field crops. Use field crops as primary evidence when they are attached for a target field, and use the full rendered PDF pages for surrounding context. Apply common-sense corrections for names, dates, addresses, and numbers. Be conservative — only change values where you are confident the correction is correct.

**Conflict resolution:** If a field crop and the full page disagree on what is written, TRUST THE CROP — the crop is a closer, higher-resolution view. Only use the full page to resolve ambiguity in the crop.

**Confidence scale:** reviewed_confidence is a float from 0.0 (completely unreadable) to 1.0 (fully confident). If you are uncertain about a correction, keep reviewed_confidence below 0.80.

**Coverage rule:** You MUST include every target field in reviewed_fields. If a field is unreadable in BOTH the attached crop AND the full page image, keep the provisional value (or empty string if none), assign low confidence, and flag it as unreadable.

**Evidence rule:** Never infer missing characters from context alone unless the image evidence strongly supports it.

Return a JSON object with this exact shape:
{{
  "reviewed_fields": [
    {{
      "field_name": "<field_name>",
      "reviewed_value": "<your corrected or confirmed value>",
      "reviewed_confidence": <0.0 to 1.0, required>,
      "reasoning": "<brief explanation, required for each field>",
      "flagged_issues": ["unreadable", "crop_page_conflict", "format_normalized", "low_confidence", "possible_ocr_error"]
    }}
  ],
  "document_notes": {{
    "readability_notes": "<optional overall note>",
    "flagged_issues": ["unreadable", "crop_page_conflict", "format_normalized", "low_confidence", "possible_ocr_error"]
  }}
}}

Rules:
- You MUST include every target field in reviewed_fields
- For each target field, always provide a non-empty reasoning string
- If you agree with the provisional value, repeat it in reviewed_value and explain why
- If attached field crops exist for a target field, inspect those crops before declaring the field unreadable
- If the attached images do not show enough evidence, say so clearly in reasoning instead of guessing
- If a field is unreadable in both crop and full page, keep the provisional value (or empty string if none), assign low confidence, and include "unreadable" in flagged_issues
- Never infer missing characters from context alone unless the image evidence strongly supports it
- reviewed_confidence MUST be between 0.0 and 1.0; if uncertain, keep it below 0.80
- Use only these flagged_issues values when relevant: unreadable, crop_page_conflict, format_normalized, low_confidence, possible_ocr_error
- Be conservative when schema context is missing
- Return valid JSON only — no extra text

Provisional extraction results:
{prov_block}
"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_gemma_response(content: str) -> "GemmaReviewResult":
    """
    Parse Gemma's JSON response and return a GemmaReviewResult.

    Degrades gracefully: if JSON cannot be parsed, returns an empty result
    and logs a warning.
    """
    try:
        data = _extract_json(content)
        if data is None:
            logger.warning(f"Gemma response did not contain valid JSON. Raw: {content[:200]!r}")
            return GemmaReviewResult(reviewed_fields=[], document_notes=[])

        reviewed_fields = []
        for item in data.get("reviewed_fields", []):
            reviewed_fields.append(
                ReviewedField(
                    field_name=item.get("field_name", ""),
                    reviewed_value=item.get("reviewed_value", ""),
                    reviewed_confidence=item.get("reviewed_confidence"),
                    reasoning=item.get("reasoning"),
                    flagged_issues=item.get("flagged_issues", []),
                )
            )

        doc_notes_raw = data.get("document_notes", {})
        # Support both legacy list format and new structured object format
        if isinstance(doc_notes_raw, list):
            document_notes = doc_notes_raw
        elif isinstance(doc_notes_raw, dict):
            notes = []
            if doc_notes_raw.get("readability_notes"):
                notes.append(doc_notes_raw["readability_notes"])
            document_notes = notes
        else:
            document_notes = []

        return GemmaReviewResult(
            reviewed_fields=reviewed_fields,
            document_notes=document_notes,
        )

    except Exception as exc:
        logger.warning(f"Failed to parse Gemma response: {exc}")
        return GemmaReviewResult(reviewed_fields=[], document_notes=[])


def _extract_json(content: str) -> Optional[dict]:
    """
    Extract a JSON object from Gemma's response text.
    Handles cases where Gemma wraps JSON in ```json ... ``` fences.
    """
    content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    for marker in ("```json", "```JSON", "```"):
        if content.startswith(marker):
            content = content[len(marker):]
            end = content.rfind("```")
            if end != -1:
                content = content[:end]
            content = content.strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ReviewedField:
    """One field's output from a Gemma whole-PDF review pass."""
    field_name: str
    reviewed_value: str
    reviewed_confidence: Optional[float] = None
    reasoning: Optional[str] = None
    flagged_issues: list = field(default_factory=list)


@dataclass
class GemmaReviewResult:
    """
    Result of a Gemma whole-PDF review call.

    Attributes
    ----------
    reviewed_fields : list[ReviewedField]
        Fields Gemma chose to revise or comment on.
    document_notes : list[str]
        Optional document-level notes from Gemma.
    error_message : str | None
        User-visible failure message when whole-document review could not run.
    """
    reviewed_fields: list[ReviewedField] = field(default_factory=list)
    document_notes: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
