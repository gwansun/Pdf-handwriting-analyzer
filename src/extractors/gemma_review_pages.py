"""Helpers for selecting and rendering relevant PDF pages for Gemma review."""

from __future__ import annotations

import base64
import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pdf2image import convert_from_path
from PIL import Image

from common.config import REVIEW_PAGE_IMAGE_DIR
from extractors.field_cropper import crop_field_region

logger = logging.getLogger("gemma_review_pages")

DEFAULT_REVIEW_DPI = 144
DEFAULT_MAX_IMAGE_DIMENSION = 1600
DEFAULT_MAX_REVIEW_PAGES = 5


@dataclass
class RenderedReviewPage:
    page_number: int
    image_url: str
    mime_type: str = "image/png"
    width: Optional[int] = None
    height: Optional[int] = None
    saved_path: Optional[str] = None


@dataclass
class ReviewPageRenderResult:
    pages: list[RenderedReviewPage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class RenderedReviewFieldCrop:
    field_name: str
    field_label: str
    page_number: int
    image_url: str
    mime_type: str = "image/png"
    width: Optional[int] = None
    height: Optional[int] = None
    saved_path: Optional[str] = None


@dataclass
class ReviewFieldCropRenderResult:
    field_crops: list[RenderedReviewFieldCrop] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error_message: Optional[str] = None


def select_relevant_review_pages(
    schema_fields: list[dict],
    review_target_fields: list[str],
    *,
    max_pages: int = DEFAULT_MAX_REVIEW_PAGES,
) -> tuple[list[int], list[str]]:
    """Return de-duplicated relevant page numbers for the target fields."""
    targets = {name for name in (review_target_fields or []) if name}
    pages: list[int] = []
    warnings: list[str] = []

    for field in schema_fields or []:
        field_name = field.get("field_name")
        if field_name not in targets:
            continue
        try:
            page_number = int(field.get("page_number", 1) or 1)
        except (TypeError, ValueError):
            page_number = 1
        if page_number not in pages:
            pages.append(page_number)

    pages.sort()

    if not pages and targets:
        warnings.append("Gemma whole-document review could not determine relevant pages from the template schema.")
        return [], warnings

    if len(pages) > max_pages:
        original_count = len(pages)
        pages = pages[:max_pages]
        warnings.append(
            f"Gemma whole-document review was limited to the first {max_pages} relevant pages out of {original_count}."
        )

    return pages, warnings


def render_review_pages(
    pdf_path: str,
    page_numbers: list[int],
    *,
    dpi: int = DEFAULT_REVIEW_DPI,
    max_dimension: int = DEFAULT_MAX_IMAGE_DIMENSION,
) -> ReviewPageRenderResult:
    """Render selected PDF pages as base64 image_url payloads for multimodal review."""
    result = ReviewPageRenderResult()

    if not page_numbers:
        result.error_message = "Gemma whole-document review could not start because no relevant PDF pages were selected."
        return result

    try:
        pdf_name = _safe_stem(pdf_path)
        REVIEW_PAGE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

        for page_number in page_numbers:
            images = convert_from_path(
                pdf_path,
                first_page=page_number,
                last_page=page_number,
                dpi=dpi,
                fmt="png",
            )
            if not images:
                result.warnings.append(
                    f"Gemma whole-document review could not render page {page_number}."
                )
                continue

            image = _resize_if_needed(images[0], max_dimension=max_dimension)
            saved_path = _save_rendered_page(image, pdf_name=pdf_name, page_number=page_number)
            image_url, width, height = _to_data_url(image)
            result.pages.append(
                RenderedReviewPage(
                    page_number=page_number,
                    image_url=image_url,
                    width=width,
                    height=height,
                    saved_path=str(saved_path),
                )
            )
            logger.info("Saved Gemma review page image: %s", saved_path)
    except Exception as exc:
        logger.warning("Failed to render review pages: %s", exc)
        result.error_message = "Gemma whole-document review could not render the relevant PDF pages."
        return result

    if not result.pages and result.error_message is None:
        result.error_message = "Gemma whole-document review could not render the relevant PDF pages."

    return result


def render_review_field_crops(
    pdf_path: str,
    schema_fields: list[dict],
    review_target_fields: list[str],
    page_sizes: Optional[list[tuple[float, float]]] = None,
    *,
    dpi: int = 300,
    max_dimension: int = 1200,
) -> ReviewFieldCropRenderResult:
    """Render per-field crops for handwritten name targets to help Gemma focus."""
    result = ReviewFieldCropRenderResult()
    targets = {name for name in (review_target_fields or []) if name}
    if not targets:
        return result

    pdf_name = _safe_stem(pdf_path)
    REVIEW_PAGE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    for field in schema_fields or []:
        field_name = field.get("field_name", "")
        if field_name not in targets:
            continue
        if field.get("field_type") != "handwritten_name":
            continue
        bbox = field.get("bbox") or []
        if len(bbox) != 4:
            result.warnings.append(f"Gemma field crop skipped for {field_name}: missing bbox.")
            continue
        try:
            page_number = int(field.get("page_number", 1) or 1)
        except (TypeError, ValueError):
            page_number = 1
        page_width, page_height = _page_size_for_number(page_sizes, page_number)
        padded_bbox = _expand_bbox(bbox, x_pad=14.0, y_pad=8.0, page_width=page_width, page_height=page_height)
        image = crop_field_region(pdf_path, page_number, padded_bbox, page_size=(page_width, page_height), dpi=dpi)
        if image is None:
            result.warnings.append(f"Gemma field crop skipped for {field_name}: crop failed.")
            continue
        image = _resize_if_needed(image, max_dimension=max_dimension)
        saved_path = _save_rendered_field_crop(image, pdf_name=pdf_name, field_name=field_name, page_number=page_number)
        image_url, width, height = _to_data_url(image)
        result.field_crops.append(
            RenderedReviewFieldCrop(
                field_name=field_name,
                field_label=field.get("field_label", "") or field_name,
                page_number=page_number,
                image_url=image_url,
                width=width,
                height=height,
                saved_path=str(saved_path),
            )
        )
        logger.info("Saved Gemma review field crop: %s", saved_path)

    return result


def _expand_bbox(
    bbox: list[float], *, x_pad: float, y_pad: float, page_width: float, page_height: float
) -> list[float]:
    x0, y0, x1, y1 = bbox
    return [
        max(0.0, x0 - x_pad),
        max(0.0, y0 - y_pad),
        min(page_width, x1 + x_pad),
        min(page_height, y1 + y_pad),
    ]


def _page_size_for_number(page_sizes: Optional[list[tuple[float, float]]], page_number: int) -> tuple[float, float]:
    page_index = max(0, int(page_number) - 1)
    if page_sizes and page_index < len(page_sizes):
        try:
            return (float(page_sizes[page_index][0]), float(page_sizes[page_index][1]))
        except Exception:
            pass
    return (612.0, 792.0)


def _resize_if_needed(image: Image.Image, *, max_dimension: int) -> Image.Image:
    width, height = image.size
    longest_side = max(width, height)
    if longest_side <= max_dimension:
        return image

    scale = max_dimension / float(longest_side)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _to_data_url(image: Image.Image) -> tuple[str, int, int]:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    width, height = image.size
    return f"data:image/png;base64,{encoded}", width, height


def _safe_stem(pdf_path: str) -> str:
    stem = Path(pdf_path).stem
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return cleaned or "review_pages"


def _save_rendered_page(image: Image.Image, *, pdf_name: str, page_number: int) -> Path:
    output_path = REVIEW_PAGE_IMAGE_DIR / f"{pdf_name}__page_{page_number}.png"
    image.save(output_path, format="PNG", optimize=True)
    return output_path


def _save_rendered_field_crop(image: Image.Image, *, pdf_name: str, field_name: str, page_number: int) -> Path:
    safe_field_name = re.sub(r"[^A-Za-z0-9._-]+", "_", field_name).strip("._-") or "field"
    output_path = REVIEW_PAGE_IMAGE_DIR / f"{pdf_name}__page_{page_number}__field_{safe_field_name}.png"
    image.save(output_path, format="PNG", optimize=True)
    return output_path
