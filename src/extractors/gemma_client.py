"""
Gemma 4 review/refine client.
Endpoint: http://127.0.0.1:11435
Used when field confidence < 0.70 to review and refine extraction.
"""
import httpx
from common.config import GEMMA_ENDPOINT, MODEL_TIMEOUT_SECONDS

def review_extraction(
    field_label: str,
    raw_text: str,
    field_type: str,
) -> tuple[str, float, str]:
    """
    Send low-confidence extraction to Gemma for review.
    Returns (refined_text, refined_confidence, reasoning).
    """
    prompt = (
        f"You are reviewing a handwritten text extraction from a government form.\n"
        f"Field: {field_label}\n"
        f"Field type: {field_type}\n"
        f"Raw extracted text: '{raw_text}'\n\n"
        f"Based on the field type and raw text, provide your best interpretation.\n"
        f"If the text is clearly readable, return it as-is.\n"
        f"If it needs correction, provide the corrected version.\n"
        f"If completely unreadable, state 'UNREADABLE'.\n\n"
        f"Return format:\n"
        f"TEXT: <your interpretation>\n"
        f"CONFIDENCE: <0.0 to 1.0>\n"
        f"REASONING: <brief explanation>"
    )
    
    payload = {
        "prompt": prompt,
        "max_tokens": 128,
        "temperature": 0.1,
    }
    
    try:
        with httpx.Client(timeout=MODEL_TIMEOUT_SECONDS) as client:
            resp = client.post(f"{GEMMA_ENDPOINT}/v1/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Parse Gemma response
            text = ""
            confidence = 0.5
            reasoning = ""
            
            for line in content.split("\n"):
                if line.startswith("TEXT:"):
                    text = line[5:].strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(line[11:].strip())
                    except:
                        pass
                elif line.startswith("REASONING:"):
                    reasoning = line[10:].strip()
            
            return text, confidence, reasoning
    except Exception as e:
        return raw_text, 0.3, f"Review failed: {e}"