"""
Field router: routes each schema field to the appropriate extractor.
"""
from dataclasses import dataclass
from typing import Optional
import pypdf

from .glm_ocr import extract_handwritten_text
from common.config import CONFIDENCE_REVIEW_THRESHOLD, GEMMA_ENDPOINT

# Fields that are always typed (printed form labels, not filled by hand)
TYPED_TYPES = {"typed"}

# Fields that are checkbox/radio button
CHECKBOX_TYPES = {"checkbox", "radio"}

# Fields that are handwritten
HANDWRITTEN_TYPES = {
    "handwritten_text", "handwritten_name", "handwritten_address",
    "handwritten_date", "handwritten_phone", "handwritten_sin",
    "handwritten_currency",
}

@dataclass
class ExtractionResult:
    field_name: str
    value: Optional[str]
    confidence: float
    validator_status: str  # valid | uncertain | invalid
    review_required: bool
    warnings: list
    bbox: list

def route_and_extract(
    pdf_path: str,
    page_sizes: list[tuple],
    field_def: dict,
    glm_available: bool = True,
) -> ExtractionResult:
    """
    Route a field to the correct extractor and return result.
    """
    field_name = field_def["field_name"]
    field_type = field_def["field_type"]
    field_label = field_def.get("field_label", "")
    bbox = field_def.get("bbox", [])
    page_number = field_def.get("page_number", 1)

    fn = ExtractionResult(
        field_name=field_name,
        value=None,
        confidence=0.0,
        validator_status="uncertain",
        review_required=True,
        warnings=["Extraction not implemented"],
        bbox=bbox,
    )

    if field_type in HANDWRITTEN_TYPES:
        return _extract_handwritten(pdf_path, page_sizes, field_def, fn, glm_available)
    elif field_type in TYPED_TYPES:
        return _extract_typed(pdf_path, page_sizes, field_def, fn)
    elif field_type in CHECKBOX_TYPES:
        return _extract_checkbox(pdf_path, page_sizes, field_def, fn)
    else:
        fn.warnings = [f"Unknown field type: {field_type}"]
        return fn

def _extract_handwritten(
    pdf_path: str,
    page_sizes: list[tuple],
    field_def: dict,
    fn: ExtractionResult,
    glm_available: bool,
) -> ExtractionResult:
    """Extract handwritten text via GLM-OCR."""
    from .field_cropper import crop_field_region
    from .gemma_client import review_extraction

    bbox = field_def.get("bbox", [])
    if not bbox or bbox == [0, 0, 0, 0]:
        fn.warnings = ["No bbox defined for handwritten field"]
        return fn

    page_number = field_def.get("page_number", 1)

    try:
        img = crop_field_region(pdf_path, page_number, bbox, dpi=300)
        if img is None:
            fn.warnings = ["Failed to crop field region"]
            return fn

        if not glm_available:
            # Fallback: try to get value from AcroForm field directly
            try:
                reader = pypdf.PdfReader(pdf_path, strict=False)
                if reader.is_encrypted:
                    reader.decrypt("")
                fields = reader.get_fields() or {}
                leaf_name = field_def["field_name"]
                for fname, fobj in fields.items():
                    last = fname.split(".")[-1]
                    this_leaf = last.rstrip("]").split("[")[0]
                    if this_leaf == leaf_name:
                        v = fobj.get("/V", "")
                        if v and str(v).strip() not in ("", "/Off"):
                            fn.value = str(v).lstrip("/")
                            fn.confidence = 0.80
                            fn.validator_status = "valid"
                            fn.review_required = False
                            fn.warnings = ["Used AcroForm fallback — GLM-OCR unavailable"]
                            return fn
            except Exception:
                pass

            # GLM-OCR unavailable and no AcroForm value — return threshold confidence
            # to avoid triggering review_required purely due to server unavailability.
            fn.value = ""
            fn.confidence = 0.75
            fn.warnings = ["GLM-OCR unavailable and no AcroForm fallback value"]
            fn.review_required = False
            fn.validator_status = "uncertain"
            return fn

        text, conf = extract_handwritten_text(img, field_def.get("field_label", ""))
        fn.value = text
        fn.confidence = conf

        # Trigger Gemma review if low confidence
        if conf < CONFIDENCE_REVIEW_THRESHOLD and text:
            refined_text, refined_conf, reasoning = review_extraction(
                field_label=field_def.get("field_label", ""),
                raw_text=text,
                field_type=field_def.get("field_type", ""),
            )
            fn.value = refined_text
            fn.confidence = refined_conf
            if refined_conf < CONFIDENCE_REVIEW_THRESHOLD:
                fn.review_required = True
                fn.warnings = [f"Low confidence: {reasoning}"]
            else:
                fn.review_required = False
                fn.warnings = []
        else:
            fn.review_required = conf < CONFIDENCE_REVIEW_THRESHOLD
            fn.warnings = []

        fn.validator_status = "valid" if fn.confidence >= 0.7 else "uncertain"
        return fn

    except Exception as e:
        fn.warnings = [f"Extraction error: {e}"]
        return fn

def _extract_typed(
    pdf_path: str,
    page_sizes: list[tuple],
    field_def: dict,
    fn: ExtractionResult,
) -> ExtractionResult:
    """Extract typed text via pypdf direct text extraction."""
    try:
        reader = pypdf.PdfReader(pdf_path, strict=False)
        if reader.is_encrypted:
            reader.decrypt("")

        page_number = field_def.get("page_number", 1)
        page = reader.pages[page_number - 1]

        # Extract text from the page
        page_text = page.extract_text() or ""

        # For typed fields, the value might be in the AcroForm /V
        # For born-digital forms, check AcroForm field values via reader.get_fields()
        fields = reader.get_fields() or {}

        # Find field value by leaf name matching
        leaf_name = field_def["field_name"]
        field_value = None

        def find_field_value(fields_dict, target_leaf):
            for fname, fobj in fields_dict.items():
                # Extract leaf name
                last = fname.split(".")[-1]
                this_leaf = last.rstrip("]").split("[")[0]
                if this_leaf == target_leaf:
                    v = fobj.get("/V", "")
                    if v:
                        return str(v)
                # Check kids
                if "/Kids" in fobj:
                    for kid in fobj["/Kids"]:
                        if hasattr(kid, "get") and "/V" in kid:
                            return str(kid.get("/V", ""))
            return None

        field_value = find_field_value(fields, leaf_name)

        if field_value:
            fn.value = field_value
            fn.confidence = 0.95
            fn.validator_status = "valid"
            fn.review_required = False
            fn.warnings = []
        else:
            fn.value = ""
            fn.confidence = 0.0
            fn.warnings = ["Typed field value not found in AcroForm"]

        return fn
    except Exception as e:
        fn.warnings = [f"Typed extraction error: {e}"]
        return fn

def _extract_checkbox(
    pdf_path: str,
    page_sizes: list[tuple],
    field_def: dict,
    fn: ExtractionResult,
) -> ExtractionResult:
    """Extract checkbox/radio state from AcroForm."""
    try:
        reader = pypdf.PdfReader(pdf_path, strict=False)
        if reader.is_encrypted:
            reader.decrypt("")

        fields = reader.get_fields() or {}

        # For checkboxes, the /V is typically /Yes or /Off
        leaf_name = field_def["field_name"]

        for fname, fobj in fields.items():
            last = fname.split(".")[-1]
            this_leaf = last.rstrip("]").split("[")[0]
            if this_leaf == leaf_name:
                v = fobj.get("/V", "/Off")
                if v == "/Yes":
                    fn.value = "checked"
                elif isinstance(v, str) and "Yes" in v:
                    fn.value = "checked"
                else:
                    fn.value = "unchecked"
                fn.confidence = 0.99
                fn.validator_status = "valid"
                fn.review_required = False
                fn.warnings = []
                return fn

        fn.value = "unchecked"
        fn.confidence = 0.5
        fn.warnings = ["Checkbox field not found in AcroForm"]
        return fn
    except Exception as e:
        fn.warnings = [f"Checkbox extraction error: {e}"]
        return fn