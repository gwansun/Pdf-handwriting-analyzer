"""
Page preprocessor: binarization and deskewing for better OCR.
"""
from PIL import Image, ImageFilter, ImageOps
from typing import Optional

def preprocess_for_ocr(img: Image.Image, field_type: str = "handwritten_text") -> Image.Image:
    """
    Apply preprocessing to improve OCR quality.
    Steps:
    1. Convert to grayscale
    2. Apply adaptive thresholding for handwritten fields
    3. Slight sharpening for handwriting
    """
    # Convert to grayscale
    gray = img.convert("L")

    # Resize if too small (for better OCR)
    w, h = gray.size
    if h < 40:
        new_h = 40
        new_w = int(w * new_h / h)
        gray = gray.resize((new_w, new_h), Image.LANCZOS)

    # For handwritten: apply adaptive threshold
    if "handwritten" in field_type.lower():
        # Convert to binary using adaptive threshold
        # Use ImageOps.autocontrast + threshold
        gray = ImageOps.autocontrast(gray, cutoff=2)

        # Simple binary threshold
        threshold = 128
        binary = gray.point(lambda x: 255 if x > threshold else 0)

        # Slight dilation to connect broken strokes
        from PIL import ImageFilter as IF
        binary = binary.filter(IF.MinFilter(3))
        return binary

    # For typed text: moderate enhancement
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.SHARPEN)
    return gray