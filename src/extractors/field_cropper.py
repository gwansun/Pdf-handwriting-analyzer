"""
Field cropper: renders PDF pages to images and crops individual field regions.
PDF coordinates: origin bottom-left, y increases up.
Image coordinates: origin top-left, y increases down.
"""
from typing import Optional

from PIL import Image
from pdf2image import convert_from_path

def crop_field_region(
    pdf_path: str,
    page_number: int,
    bbox_pdf: list[float],  # [x0, y0, x1, y1] in PDF points
    page_size: Optional[tuple[float, float]] = None,
    dpi: int = 300,
) -> Optional[Image.Image]:
    """
    Render a PDF page at given DPI and crop the field region.
    Returns PIL Image of the cropped field.

    PDF y-coords are bottom-left origin; image y-coords are top-left.
    """
    try:
        # Convert PDF page to image at specified DPI
        images = convert_from_path(
            pdf_path,
            first_page=page_number,
            last_page=page_number,
            dpi=dpi,
            fmt="png",
        )
        if not images:
            return None

        page_img = images[0]
        img_w, img_h = page_img.size

        # Prefer actual page size from schema/inspection; otherwise derive from rendered image.
        scale = dpi / 72.0
        if page_size and len(page_size) == 2:
            _pdf_w, pdf_h = float(page_size[0]), float(page_size[1])
        else:
            pdf_h = img_h / scale

        # Convert PDF coords to image coords
        # x: linear (same scale)
        # y: flip - PDF y=0 (bottom) → image y=img_h; PDF y=pdf_h (top) → image y=0
        x0, y0, x1, y1 = bbox_pdf

        # Scale factor (DPI / 72 pts per inch)

        # Image crop box: [left, top, right, bottom] in pixels
        crop_x0 = int(x0 * scale)
        crop_y0 = int((pdf_h - y1) * scale)  # top of bbox in image coords
        crop_x1 = int(x1 * scale)
        crop_y1 = int((pdf_h - y0) * scale)  # bottom of bbox in image coords

        # Clamp to image bounds
        crop_x0 = max(0, min(crop_x0, img_w))
        crop_x1 = max(0, min(crop_x1, img_w))
        crop_y0 = max(0, min(crop_y0, img_h))
        crop_y1 = max(0, min(crop_y1, img_h))

        if crop_x1 <= crop_x0 or crop_y1 <= crop_y0:
            return None

        cropped = page_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
        return cropped

    except Exception:
        return None