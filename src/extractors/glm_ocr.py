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
    
    prompt = (
        "You are an expert at reading handwritten text on forms. "
        "Read ALL handwritten text visible in this image carefully. "
        "Return ONLY the text you can read, with minimal formatting. "
        "If the field appears empty or unreadable, return an empty string.\n"
    )
    if field_label:
        prompt += f"Field context: {field_label}\n"
    prompt += "Read the text now:"
    
    payload = {
        "prompt": prompt,
        "image": f"data:image/png;base64,{img_b64}",
        "max_tokens": 256,
        "temperature": 0.1,
    }
    
    try:
        with httpx.Client(timeout=MODEL_TIMEOUT_SECONDS) as client:
            resp = client.post(f"{GLM_OCR_ENDPOINT}/v1/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Parse response - GLM-OCR returns text content
            text = content.strip()
            
            # Simple confidence heuristic
            if not text:
                return "", 0.0
            if "unreadable" in text.lower() or "empty" in text.lower():
                return "", 0.3
            return text, 0.75
    except Exception as e:
        return "", 0.0