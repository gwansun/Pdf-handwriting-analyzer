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
from typing import Optional

from common.config import GEMMA_ENDPOINT, MODEL_TIMEOUT_SECONDS

logger = logging.getLogger("gemma_client")


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
    # Trigger inputs
    average_document_confidence: float = 0.0,
    review_target_fields: Optional[list[str]] = None,
) -> "GemmaReviewResult":
    """
    Invoke Gemma once for the whole PDF to review first-pass extraction results.

    Parameters
    ----------
    review_mode : str
        "matched_template_review" or "fallback_review"
    gemma_available : bool
        If False, return an empty result without calling the server.
    template : dict, optional
        Template manifest (template_id, template_family, display_name, template_version,
        runtime_hints).
    schema_fields : list[dict], optional
        List of field definitions from the schema (field_name, field_label,
        field_type, page_number, bbox, options).
    first_pass_results : list[dict], optional
        List of first-pass extraction results (field_name, value, confidence,
        review_required, warnings).
    document : dict, optional
        Basic document info (page_count, average_document_confidence, metadata).
    inspection : dict, optional
        PDF inspection signals (is_born_digital, is_scanned, is_hybrid,
        acroform_field_names).
    provisional_results : list[dict], optional
        Provisional extraction results (for fallback path).
    warnings : list[str], optional
        Warning strings to include in the fallback payload.
    average_document_confidence : float
        Average first-pass confidence across all fields.
    review_target_fields : list[str], optional
        Field names that Gemma should specifically review.

    Returns
    -------
    GemmaReviewResult
        reviewed_fields: list of ReviewedField
        document_notes: list of str
    """
    if not gemma_available:
        logger.warning("Gemma unavailable — skipping document review")
        return GemmaReviewResult(reviewed_fields=[], document_notes=[])

    if review_mode == "matched_template_review":
        payload = _build_matched_template_payload(
            template=template,
            schema_fields=schema_fields,
            first_pass_results=first_pass_results,
            average_document_confidence=average_document_confidence,
            review_target_fields=review_target_fields,
        )
    elif review_mode == "fallback_review":
        payload = _build_fallback_payload(
            document=document,
            inspection=inspection,
            provisional_results=provisional_results,
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
        "review_target_fields": review_target_fields or [],
    }


def _build_fallback_payload(
    document: dict,
    inspection: dict,
    provisional_results: list[dict],
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
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1500,
        "temperature": 0.1,
    }

    try:
        with httpx.Client(timeout=MODEL_TIMEOUT_SECONDS) as client:
            resp = client.post(
                f"{GEMMA_ENDPOINT}/v1/chat/completions",
                json=request_payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return _parse_gemma_response(content)

    except Exception as exc:
        logger.warning(f"Gemma review call failed: {exc}")
        return GemmaReviewResult(reviewed_fields=[], document_notes=[])


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
    avg_conf = payload.get("document", {}).get("average_document_confidence", 0.0)
    targets = payload.get("review_target_fields", [])

    schema_block = json.dumps(schema_fields, indent=2)
    first_pass_block = json.dumps(first_pass, indent=2)
    targets_list = ", ".join(targets) if targets else "all low-confidence fields"

    return f"""You are reviewing handwritten text extractions from a government form.

Document info:
- Template: {template.get('display_name', 'Unknown')} ({template.get('template_id', '')})
- Average document confidence: {avg_conf:.2f}

Your task:
Review the first-pass extraction results below. For each field in {targets_list}, compare your understanding of the document against the extracted value. Correct any obvious OCR errors, normalize formatting (e.g. names, dates, SINs), and flag truly unreadable fields.

Return a JSON object with this exact shape:
{{
  "reviewed_fields": [
    {{
      "field_name": "<field_name>",
      "reviewed_value": "<your corrected or confirmed value>",
      "reviewed_confidence": <0.0 to 1.0, optional>,
      "reasoning": "<brief explanation, optional>"
    }}
  ],
  "document_notes": ["<optional note about the document>"]
}}

Rules:
- Only include fields you want to revise or comment on
- Fields omitted from reviewed_fields keep their first-pass value unchanged
- If a field is unreadable, set reviewed_value to the first-pass value and note it
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
    avg_conf = doc.get("average_document_confidence", 0.0)
    targets = payload.get("review_target_fields", [])
    warnings = payload.get("warnings", [])

    prov_block = json.dumps(prov, indent=2) if prov else "[]"
    warnings_block = "\n".join(f"- {w}" for w in warnings) if warnings else "None"

    return f"""You are reviewing text extractions from a PDF document where no template metadata is available.

Document info:
- Page count: {doc.get('page_count', 'unknown')}
- Average document confidence: {avg_conf:.2f}
- Classification: born_digital={insp.get('is_born_digital')}, scanned={insp.get('is_scanned')}, hybrid={insp.get('is_hybrid')}
- AcroForm fields: {insp.get('acroform_field_names', [])}
- Warnings: {warnings_block}

Your task:
Review the provisional extraction results. Apply common-sense corrections for names, dates, addresses, and numbers. Be conservative — only change values where you are confident the correction is correct.

Return a JSON object with this exact shape:
{{
  "reviewed_fields": [
    {{
      "field_name": "<field_name>",
      "reviewed_value": "<your corrected or confirmed value>",
      "reviewed_confidence": <0.0 to 1.0, optional>,
      "reasoning": "<brief explanation, optional>"
    }}
  ],
  "document_notes": ["<optional note about the document>"]
}}

Rules:
- Only include fields you want to revise or comment on
- Fields omitted keep their first-pass value unchanged
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
        # Try to extract JSON from the response content
        data = _extract_json(content)
        if data is None:
            logger.warning("Gemma response did not contain valid JSON")
            return GemmaReviewResult(reviewed_fields=[], document_notes=[])

        reviewed_fields = []
        for item in data.get("reviewed_fields", []):
            reviewed_fields.append(
                ReviewedField(
                    field_name=item.get("field_name", ""),
                    reviewed_value=item.get("reviewed_value", ""),
                    reviewed_confidence=item.get("reviewed_confidence"),
                    reasoning=item.get("reasoning"),
                )
            )

        document_notes = data.get("document_notes", [])
        if isinstance(document_notes, str):
            document_notes = [document_notes]

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

    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try stripping code fences
    for marker in ("```json", "```JSON", "```"):
        if content.startswith(marker):
            content = content[len(marker):]
            # Strip the closing fence too
            end = content.rfind("```")
            if end != -1:
                content = content[:end]
            content = content.strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

    # Try finding the first { and last }
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

from dataclasses import dataclass, field


@dataclass
class ReviewedField:
    """One field's output from a Gemma whole-PDF review pass."""
    field_name: str
    reviewed_value: str
    reviewed_confidence: Optional[float] = None
    reasoning: Optional[str] = None


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
    """
    reviewed_fields: list[ReviewedField] = field(default_factory=list)
    document_notes: list[str] = field(default_factory=list)
