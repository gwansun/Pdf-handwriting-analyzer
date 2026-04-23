# MARKER_V5_CHECK
"""
Field router: routes each schema field to the appropriate extractor.
"""
from dataclasses import dataclass
from typing import Optional
import pypdf

from .glm_ocr import extract_handwritten_text
from common.config import CONFIDENCE_REVIEW_THRESHOLD

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

    Note: gemma_available is no longer a parameter — Gemma review is no longer
    called from field routing. Document-level Gemma review is handled in main.py.
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
        return _extract_checkbox(pdf_path, page_sizes, field_def, fn, glm_available)
    else:
        fn.warnings = [f"Unknown field type: {field_type}"]
        return fn


def _get_acroform_value(
    pdf_path: str,
    page_number: int,
    field_def: dict,
) -> Optional[str]:
    """Extract a field value from AcroForm data."""
    try:
        reader = pypdf.PdfReader(pdf_path, strict=False)
        if reader.is_encrypted:
            reader.decrypt("")
        fields = reader.get_fields() or {}
        leaf_name = field_def.get("field_name", "")
        for fname, fobj in fields.items():
            last = fname.split(".")[-1]
            this_leaf = last.rstrip("]").split("[")[0]
            if this_leaf == leaf_name:
                v = fobj.get("/V", "")
                if v and str(v).strip() not in ("", "/Off"):
                    return str(v).lstrip("/")
        return None
    except Exception:
        return None


def _extract_handwritten(
    pdf_path: str,
    page_sizes: list[tuple],
    field_def: dict,
    fn: ExtractionResult,
    glm_available: bool,
) -> ExtractionResult:
    """Extract handwritten text via GLM-OCR.

    Gemma review is no longer called here. Instead, after all fields are
    extracted, the document-level average confidence is computed in main.py
    and Gemma is called once per PDF if it is below the review threshold.
    """
    from .field_cropper import crop_field_region

    bbox = field_def.get("bbox", [])
    if not bbox or bbox == [0, 0, 0, 0]:
        fn.warnings = ["No bbox defined for handwritten field"]
        return fn

    page_number = field_def.get("page_number", 1)

    try:
        img = crop_field_region(pdf_path, page_number, bbox, dpi=300)

        if img is None:
            # Poppler/pdf2image not available — can't render the page.
            # Fall back: try page-level pypdf text extraction.
            fn.warnings = ["Crop failed — pdf2image/poppler unavailable; used page-level extraction fallback"]
            return _fallback_page_extraction(pdf_path, page_number, field_def, fn)

        if not glm_available:
            # GLM-OCR unavailable — use page-level extraction as last resort
            fn.warnings = ["GLM-OCR unavailable; used page-level extraction fallback"]
            return _fallback_page_extraction(pdf_path, page_number, field_def, fn)

        text, conf = extract_handwritten_text(img, field_def.get("field_label", ""))
        fn.value = text
        fn.confidence = conf

        # If GLM returned blank but we have an AcroForm value, use it
        if not text and conf <= 0.3:
            acroform_value = _get_acroform_value(pdf_path, page_number, field_def)
            if acroform_value:
                fn.value = acroform_value
                fn.confidence = 0.85
                fn.validator_status = "valid"
                fn.review_required = False
                fn.warnings = ["Born-digital form field — used AcroForm value"]
                return fn

        # Set review_required based solely on GLM confidence — Gemma review
        # happens once per document in main.py, not per-field here.
        fn.review_required = conf < CONFIDENCE_REVIEW_THRESHOLD
        fn.warnings = []
        fn.validator_status = "valid" if conf >= CONFIDENCE_REVIEW_THRESHOLD else "uncertain"
        return fn

    except Exception as e:
        fn.warnings = [f"Extraction error: {e}"]
        return fn


def _fallback_page_extraction(
    pdf_path: str,
    page_number: int,
    field_def: dict,
    fn: ExtractionResult,
) -> ExtractionResult:
    """
    Fallback extraction when crop fails or GLM-OCR is unavailable.
    Uses page-level pypdf text extraction to find the field value.
    """
    try:
        reader = pypdf.PdfReader(pdf_path, strict=False)
        if reader.is_encrypted:
            reader.decrypt("")
        page = reader.pages[page_number - 1]
        page_text = page.extract_text() or ""

        # Try AcroForm field value
        fields = reader.get_fields() or {}
        leaf_name = field_def["field_name"]
        field_value = None

        for fname, fobj in fields.items():
            last = fname.split(".")[-1]
            this_leaf = last.rstrip("]").split("[")[0]
            if this_leaf == leaf_name:
                v = fobj.get("/V", "")
                if v and str(v).strip() not in ("", "/Off"):
                    field_value = str(v).lstrip("/")
                    break

        if field_value:
            fn.value = field_value
            fn.confidence = 0.85
            fn.validator_status = "valid"
            fn.review_required = False
            fn.warnings.append("AcroForm value found via page-level fallback")
            return fn

        # No AcroForm value — try page text extraction
        # For blank forms, page text will be the printed form labels, not filled data
        field_label = field_def.get("field_label", "")
        if page_text and field_label:
            # Check if the printed label appears in page text
            # This tells us the field slot exists but is empty
            if field_label.lower()[:20] in page_text.lower():
                fn.value = ""
                fn.confidence = 0.65
                fn.validator_status = "uncertain"
                fn.review_required = True
                fn.warnings.append("Field slot confirmed via page text; value empty (blank form)")
                return fn

        # Blank — no printed label found either
        fn.value = ""
        fn.confidence = 0.50
        fn.validator_status = "uncertain"
        fn.review_required = True
        fn.warnings.append("Blank/unreadable field — no value in AcroForm or page text")
        return fn

    except Exception as e:
        fn.warnings.append(f"Fallback extraction error: {e}")
        fn.confidence = 0.0
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
        page_text = page.extract_text() or ""

        # For typed fields, the value might be in the AcroForm /V
        # For born-digital forms, check AcroForm field values via reader.get_fields()
        fields = reader.get_fields() or {}

        # Find field value by leaf name matching
        leaf_name = field_def["field_name"]
        field_value = None

        def find_field_value(fields_dict, target_leaf):
            for fname, fobj in fields_dict.items():
                last = fname.split(".")[-1]
                this_leaf = last.rstrip("]").split("[")[0]
                if this_leaf == target_leaf:
                    v = fobj.get("/V", "")
                    if v:
                        return str(v)
                    # No /V at this level — check kids ONLY if this IS the target field
                    if "/Kids" in fobj:
                        for kid in fobj["/Kids"]:
                            if hasattr(kid, "get") and "/V" in kid:
                                return str(kid.get("/V", ""))
                    return None
            return None

        field_value = find_field_value(fields, leaf_name)

        if field_value:
            fn.value = field_value
            fn.confidence = 0.95
            fn.validator_status = "valid"
            fn.review_required = False
            fn.warnings = []
            return fn
        else:
            # No AcroForm value — use page-level fallback to check if field is blank
            fn.value = ""
            fn.confidence = 0.65
            fn.validator_status = "uncertain"
            fn.review_required = True
            fn.warnings = ["Typed field value not found in AcroForm — confirmed blank via page text"]
            return fn
    except Exception as e:
        fn.warnings = [f"Typed extraction error: {e}"]
        return fn


def _build_page_idx_map(pdf_path: str) -> dict[str, int]:
    """Build a mapping of field /T values to page numbers by scanning
    page annotations. pypdf doesn't expose widget→page reliably via
    /P references, so we do it by /T name uniqueness assumption: each
    widget annotation on page N has /T matching an AcroForm leaf name.
    Returns a dict of leaf_name → page_number (1-indexed).
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path, strict=False)
        if reader.is_encrypted:
            reader.decrypt("")
        page_map: dict[str, int] = {}
        for page_idx, page in enumerate(reader.pages):
            if "/Annots" not in page:
                continue
            annots = page["/Annots"]
            for annot_ref in annots:
                annot = annot_ref.get_object() if hasattr(annot_ref, "get_object") else annot_ref
                if not hasattr(annot, "get"):
                    continue
                if annot.get("/Subtype") != "/Widget":
                    continue
                t = annot.get("/T")
                if t and t not in page_map:
                    page_map[str(t)] = page_idx + 1  # 1-indexed
        return page_map
    except Exception:
        return {}


def _extract_checkbox(
    pdf_path: str,
    page_sizes: list[tuple],
    field_def: dict,
    fn: ExtractionResult,
    glm_available: bool = True,
) -> ExtractionResult:
    """Extract checkbox/radio state from AcroForm.

    Handles two conventions:
    - Checkbox style: /V is /Yes (checked) or /Off (unchecked)
    - Radio button style: /V is /0, /1, /2 … indexing into /Opt array,
      or named exports like /Yes, /No

    For scanned paper forms where /V=None (neither bubble was digitally
    filled), crops each widget bubble from the rendered page and runs
    GLM-OCR to detect the presence of a hand-drawn mark.

    Supports two matching modes:
    - Default: matches by leaf name (e.g. "Q1_RadioButtonGroup") — returns
      the FIRST match found. Use when each leaf name is unique.
    - full_acroform_path: when field_def contains this key, matches the
      exact AcroForm field path. Use to disambiguate multiple instances
      that share the same leaf name.
    """
    try:
        reader = pypdf.PdfReader(pdf_path, strict=False)
        if reader.is_encrypted:
            reader.decrypt("")

        fields = reader.get_fields() or {}

        leaf_name = field_def["field_name"]
        full_path = field_def.get("full_acroform_path")
        options = field_def.get("options", [])
        # When multiple_instances=True, accumulate ALL matching fields
        # rather than returning on first match. Used for radio groups
        # where the same leaf name appears in multiple form locations.
        # acroform_leaf_name overrides leaf_name when the AcroForm leaf
        # differs from the schema field_name (e.g. schema uses
        # "Q3_Conditions_Item1_Radio" but AcroForm leaf is "Q3_RadioButtonGroup")
        acroform_leaf_name = field_def.get("acroform_leaf_name")
        match_name = acroform_leaf_name if acroform_leaf_name else leaf_name
        multiple_instances = field_def.get("multiple_instances", False)

        matched_values = []

        for fname, fobj in fields.items():
            last = fname.split(".")[-1]
            this_leaf = last.rstrip("]").split("[")[0]

            # Exact full-path match when specified
            if full_path:
                if fname != full_path:
                    continue
            else:
                if this_leaf != match_name:
                    continue

            v = fobj.get("/V", "/Off")
            opt = fobj.get("/Opt", [])

            # ---- Checkbox-style: /Yes or /Off ----
            v_str = str(v) if hasattr(v, "startswith") else v
            if v_str == "/Yes" or (isinstance(v, str) and "Yes" in v):
                val = "checked"
                if not multiple_instances:
                    fn.value = val
                    fn.confidence = 0.99
                    fn.validator_status = "valid"
                    fn.review_required = False
                    fn.warnings = []
                    return fn
                matched_values.append(val)
                if not multiple_instances:
                    break

            if v_str == "/Off":
                val = "unchecked"
                if not multiple_instances:
                    fn.value = val
                    fn.confidence = 0.99
                    fn.validator_status = "valid"
                    fn.review_required = False
                    fn.warnings = []
                    return fn
                matched_values.append(val)
                if not multiple_instances:
                    break

            # ---- Radio-button-style: /0, /1, /2 … indexing into /Opt ----
            if v_str.startswith("/"):
                idx_str = v_str.lstrip("/")
                try:
                    idx = int(idx_str)
                except ValueError:
                    idx = -1

                if options:
                    label = options[idx]["label"] if idx < len(options) else v_str
                elif opt and idx < len(opt):
                    label = opt[idx]
                else:
                    label = v_str

                if not multiple_instances:
                    fn.value = label
                    fn.confidence = 0.99
                    fn.validator_status = "valid"
                    fn.review_required = False
                    fn.warnings = []
                    return fn
                matched_values.append(label)
                if not multiple_instances:
                    break

        # Process accumulated values
        if multiple_instances and matched_values:
            fn.value = matched_values if len(matched_values) > 1 else matched_values[0]
            fn.confidence = 0.99
            fn.validator_status = "valid"
            fn.review_required = False
            fn.warnings = []
            return fn

        # No AcroForm value found — this can happen on scanned paper forms
        # where the bubble was filled by hand but /V was never set.
        # Fall back: crop the widget bubble(s) and run GLM-OCR to detect marks.
        if glm_available and not matched_values:
            ocr_result = _ocr_radio_widget(pdf_path, fields, fname, match_name, field_def)
            if ocr_result is not None:
                label, conf = ocr_result
                fn.value = label
                fn.confidence = conf
                fn.validator_status = "uncertain" if conf < 0.8 else "valid"
                fn.review_required = conf < 0.8
                fn.warnings = ["Handwritten mark detected via GLM-OCR" if label != "unchecked" else "No mark detected via GLM-OCR"]
                return fn

        # No match found
        fn.value = "unchecked"
        fn.confidence = 0.5
        fn.warnings = ["Radio/checkbox field not found in AcroForm or no value set"]
        return fn
    except Exception as e:
        fn.warnings = [f"Checkbox extraction error: {e}"]
        return fn


def _ocr_radio_widget(
    pdf_path: str,
    fields: dict,
    matched_fname: str,
    match_name: str,
    field_def: dict,
) -> Optional[tuple[str, float]]:
    """Crop the widget bubble(s) for a radio button and run GLM-OCR.

    Returns (value_label, confidence) where value_label is the checked
    option label (e.g. "Yes") or "unchecked", or None if OCR failed.

    For radio buttons with 2 options (typically Yes/No), we crop both
    bubbles. The one with the stronger GLM-OCR "text detected" response
    wins. If neither shows text, returns ("unchecked", confidence).
    """
    from .field_cropper import crop_field_region
    from .glm_ocr import extract_handwritten_text

    options = field_def.get("options", [])
    opt_count = len(options)
    if opt_count == 0:
        return None

    # Find the field object
    fobj = fields.get(matched_fname)
    if fobj is None:
        for fname, f in fields.items():
            if fname == matched_fname:
                fobj = f
                break
    if fobj is None:
        return None

    kids = fobj.get("/Kids", [])
    if not kids:
        return None

    # Resolve page number from the widget kid's /P reference.
    # pypdf page objects don't compare easily with reader.pages, so we
    # resolve to a 1-indexed page number by checking /P against each page.
    def _resolve_page_idx(pdf_path: str, page_obj) -> int:
        try:
            reader2 = pypdf.PdfReader(pdf_path, strict=False)
            if reader2.is_encrypted:
                reader2.decrypt("")
            for idx, pg in enumerate(reader2.pages):
                pg_obj = pg.get_object() if hasattr(pg, "get_object") else pg
                po = page_obj.get_object() if hasattr(page_obj, "get_object") else page_obj
                if str(pg_obj) == str(po):
                    return idx + 1
        except Exception:
            pass
        return field_def.get("page_number", 1)

    # Collect kid rects and their page numbers
    kid_data: list[dict] = []
    for kid_ref in kids:
        kid = kid_ref.get_object() if hasattr(kid_ref, "get_object") else kid_ref
        if not hasattr(kid, "get"):
            continue
        rect = kid.get("/Rect")
        if not rect:
            continue
        pg_ref = kid.get("/P")
        page_number = _resolve_page_idx(pdf_path, pg_ref) if pg_ref else field_def.get("page_number", 1)
        kid_data.append({"rect": list(rect), "page": page_number})

    if not kid_data:
        return None

    def _crop_and_ocr(rect: list[float], pg_num: int) -> tuple[str, float]:
        """Crop a rect and run GLM-OCR. Returns (detected_text, score)."""
        img = crop_field_region(pdf_path, pg_num, rect, dpi=300)
        if img is None:
            return "", 0.0
        text, conf = extract_handwritten_text(img, field_def.get("field_label", ""))
        return text, conf

    # Score each kid bubble
    # For radio buttons only ONE should be checked — take the one with
    # the highest score. If no bubble scores above threshold, it's blank.
    best_idx = -1
    best_score = 0.0
    best_text = ""

    for i, kd in enumerate(kid_data):
        text, score = _crop_and_ocr(kd["rect"], kd["page"])
        if score > best_score:
            best_score = score
            best_idx = i
            best_text = text

    # If nothing detected above threshold, it's blank
    if best_idx < 0 or best_score < 0.3:
        return ("unchecked", 0.6)

    # Map best kid index to option label
    # Kids order maps to /Opt order: kids[0] = /Opt[0]
    option_label = options[best_idx]["label"] if best_idx < opt_count else "checked"

    # If GLM says "blank" or "no text" for the best match, it's unchecked
    lower = best_text.lower().strip().lstrip("(blank).").strip()
    if not lower or any(
        kw in lower for kw in ["blank", "no text", "nothing", "empty", "unreadable"]
    ):
        return ("unchecked", 0.6)

    return (option_label, min(best_score, 0.95))
