"""
GLM-OCR client for handwritten field extraction.
Endpoint: http://127.0.0.1:11436
"""
import base64
import logging
import httpx
from PIL import Image
from io import BytesIO
from common.config import GLM_OCR_ENDPOINT, MODEL_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Max image dimension before encoding to avoid huge base64 payloads
MAX_IMAGE_DIMENSION = 1024


def encode_image_pil(img: Image.Image, fmt: str = "PNG") -> str:
    """Encode PIL image to base64 string, resizing to MAX_IMAGE_DIMENSION if needed."""
    img = _resize_if_large(img)
    buf = BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _resize_if_large(img: Image.Image) -> Image.Image:
    """Resize image if either dimension exceeds MAX_IMAGE_DIMENSION, preserving aspect ratio."""
    w, h = img.size
    if max(w, h) <= MAX_IMAGE_DIMENSION:
        return img
    ratio = min(MAX_IMAGE_DIMENSION / w, MAX_IMAGE_DIMENSION / h)
    new_size = (int(w * ratio), int(h * ratio))
    return img.resize(new_size, Image.LANCZOS)


def extract_handwritten_text(image: Image.Image, field_label: str = "") -> tuple[str, float]:
    """
    Extract handwritten text from a PIL image region using GLM-OCR.
    Returns (text, confidence).

    Prompt strategy mirrors Gemma's focused field-review approach:
    - Name the specific form field so the model anchors to the right region
    - Explicitly say "Do NOT read printed labels" to avoid form-field-label
      interference (a known failure mode when a label like "Last name:"
      sits inside or immediately adjacent to the crop)
    - "Output ONLY the handwritten text" keeps the response clean and minimal
    """
    img_b64 = encode_image_pil(image)

    user_content = []
    if field_label:
        instruction = (
            f"This image shows the '{field_label}' field on a government form. "
            f"Read ONLY the handwritten text written in this specific field box. "
            f"Do NOT read printed field labels or text from other fields or rows. "
            f"Output exactly what is written here, or (blank) if empty."
        )
    else:
        instruction = (
            "Read the handwritten text in this image. "
            "Output ONLY the handwritten text, or (blank) if empty."
        )
    user_content.append({"type": "text", "text": instruction})
    user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}})

    payload = {
        "model": "mlx-community/GLM-OCR-bf16",
        "messages": [
            {
                "role": "user",
                "content": user_content,
            }
        ],
        "max_tokens": 512,
        "temperature": 0.1,
    }

    try:
        with httpx.Client(timeout=MODEL_TIMEOUT_SECONDS) as client:
            resp = client.post(f"{GLM_OCR_ENDPOINT}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

            # Validate choices structure before accessing
            choices = data.get("choices")
            if not choices or not isinstance(choices, list) or len(choices) == 0:
                error_msg = data.get("error", {})
                logger.error("GLM-OCR returned no choices. Error: %s", error_msg)
                raise ValueError(f"GLM-OCR API error: {error_msg.get('message', 'No choices returned')}")

            message = choices[0].get("message", {})
            content = message.get("content", "")

            # Parse response
            text = content.strip()

            # Confidence heuristic based on response quality
            if not text:
                return "", 0.0

            # Detect unambiguous empty/blank responses (word-boundary-aware)
            lower = text.lower()
            # Match exact blank indicators, avoiding partial-word false positives
            blank_phrases = [
                "(blank)", "(empty)", "no text", "no handwritten",
                "nothing written", "unreadable", "cannot read", "illegible",
            ]
            if any(phrase in lower for phrase in blank_phrases):
                return "", 0.2

            # Substantial response for a field that has content → moderate-high
            return text, 0.80

    except httpx.TimeoutException:
        logger.error("GLM-OCR request timed out after %ss", MODEL_TIMEOUT_SECONDS)
        raise
    except httpx.HTTPStatusError as e:
        logger.error("GLM-OCR HTTP error: %s", e.response.status_code)
        raise
    except (ValueError, KeyError) as e:
        logger.error("GLM-OCR response parse error: %s", e)
        raise
    except Exception as e:
        logger.error("GLM-OCR unexpected error: %s", e)
        raise
