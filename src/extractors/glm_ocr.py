"""
GLM-OCR client for handwritten field extraction.
Endpoint: http://127.0.0.1:11436
"""
import base64
import httpx
from PIL import Image
from io import BytesIO
from common.config import GLM_OCR_ENDPOINT, MODEL_TIMEOUT_SECONDS

def encode_image_pil(img: Image.Image, fmt: str = "PNG") -> str:
    """Encode PIL image to base64 string."""
    buf = BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def extract_handwritten_text(image: Image.Image, field_label: str = "") -> tuple[str, float]:
    """
    Extract handwritten text from a PIL image region using GLM-OCR.
    Returns (text, confidence).
    """
    img_b64 = encode_image_pil(image)
    
    # Build prompt with field context inline
    user_content = []
    instruction = "OCR this handwritten text. Output ONLY the text, nothing else. If blank, output: (blank)."
    if field_label:
        instruction += f"  Form field: {field_label}"
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
        "max_tokens": 256,
        "temperature": 0.1,
    }

    try:
        with httpx.Client(timeout=MODEL_TIMEOUT_SECONDS) as client:
            resp = client.post(f"{GLM_OCR_ENDPOINT}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse response - strip any echoed instruction text
            text = content.strip()

            # Confidence heuristic based on response quality
            if not text:
                return "", 0.0

            # Detect unambiguous empty/blank responses
            lower = text.lower()
            if any(phrase in lower for phrase in [
                "no text", "no handwritten", "nothing", "blank",
                "empty", "unreadable", "cannot read", "illegible",
            ]):
                return "", 0.2

            # Substantial response for a field that has content → moderate-high
            return text, 0.80
    except Exception as e:
        return "", 0.0