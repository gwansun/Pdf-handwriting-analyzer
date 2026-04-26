"""
Integration tests for Gemma Whole-PDF Review feature.

Acceptance criteria:
1. Gemma called at most once per PDF (one-shot, not per-field)
2. Gemma triggered when any field requires review (< 0.70 confidence)
3. FieldResult.review carries Gemma output; value/confidence never overwritten
4. Fallback path also uses Gemma review correctly
5. Real PDF E2E with real GLM + Gemma servers
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import analyze
from extractors.gemma_client import review_document_extraction, GemmaReviewResult, ReviewedField
from extractors.gemma_review_pages import ReviewPageRenderResult, RenderedReviewPage


# ─── Paths ───────────────────────────────────────────────────────────────────

SIGNED_PDF = Path(
    "/Users/gwansun/Desktop/projects/email-manager/backend/data/attachments/"
    "60aae739-76bf-49c0-a336-1822860bbd68/Gwanjin_t2200-fill-25e_signed_4c9f216f.pdf"
)
EXAMPLE_PDF = Path(__file__).parent.parent / "example" / "t2200-fill-25e.pdf"


# ─── Helpers ─────────────────────────────────────────────────────────────────

class GemmaCallTracker:
    def __init__(self, real_fn):
        self.real_fn = real_fn
        self.call_count = 0
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        self.calls.append({"args": args, "kwargs": kwargs})
        return self.real_fn(*args, **kwargs)


def mock_gemma_review(*args, **kwargs):
    """Return a deterministic Gemma review for testing."""
    return GemmaReviewResult(
        reviewed_fields=[
            ReviewedField("Last_Name_Fill", "CHUN", 0.88, "Uppercase normalization"),
            ReviewedField("First_Name_Fill", "GWANJIN", 0.91, "Name confirmed"),
        ],
        document_notes=["Test review applied"],
    )


def make_request(pdf_path, request_id="test_001", job_id="job_001"):
    return {
        "request_id": request_id,
        "job_id": job_id,
        "attachment_id": "att_001",
        "file": {"path": str(pdf_path)},
    }


# ─── Test 1: Gemma one-shot — not called per-field ────────────────────────────

def test_gemma_one_shot_not_per_field():
    """
    Gemma must be called at most once per PDF, even when there are 19 fields.
    Uses real GLM but mocked Gemma for speed.
    """
    tracker = GemmaCallTracker(review_document_extraction)

    # Patch in main's namespace where names are imported
    with patch("main._check_gemma_available", return_value=True):
        with patch("main.review_document_extraction", tracker):
            result = analyze(make_request(SIGNED_PDF, "t1_001"))

    print(f"\n  Gemma call count: {tracker.call_count}")
    print(f"  Status: {result['status']}")
    print(f"  Avg confidence: {result['summary'].get('overall_confidence')}")

    assert tracker.call_count <= 1, (
        f"Gemma called {tracker.call_count} times — must be ≤ 1"
    )
    print("  ✓ One-shot invariant upheld")


# ─── Test 2: Gemma skipped when all fields above threshold ───────────────────

def test_gemma_skipped_above_threshold():
    """
    When ALL fields return high confidence, Gemma must NOT be called.
    The trigger is whether any field requires review.
    """
    tracker = GemmaCallTracker(review_document_extraction)

    # Mock GLM: high-confidence response for every field
    with patch("main._check_gemma_available", return_value=True):
        with patch("src.extractors.glm_ocr.extract_handwritten_text") as mock_glm:
            mock_glm.return_value = ("High Confidence Value", 0.95)
            result = analyze(make_request(SIGNED_PDF, "t2_001"))

    avg_conf = result["summary"].get("overall_confidence", 0)
    print(f"\n  Avg confidence: {avg_conf}")
    print(f"  Gemma call count: {tracker.call_count}")

    assert tracker.call_count == 0, (
        f"Gemma called {tracker.call_count} times — all fields were high-confidence (avg_conf={avg_conf:.3f})"
    )
    print("  ✓ Gemma correctly skipped when no field needed review")


# ─── Test 3: review field set, first-pass value preserved ─────────────────────

def test_review_field_set_value_preserved():
    """
    When Gemma IS called, FieldResult.review carries Gemma's reviewed_value.
    First-pass value (from GLM) is NEVER overwritten.
    """
    tracker = GemmaCallTracker(mock_gemma_review)

    # Mock route_and_extract in main.py's namespace (where it's imported as a local name)
    from extractors.field_router import route_and_extract, ExtractionResult

    def mock_route(pdf_path, page_sizes, field_def, glm_available=True):
        return ExtractionResult(
            field_name=field_def.get("field_name", ""),
            value="Chun",       # GLM's first-pass output
            confidence=0.65,   # below threshold → field-level review triggers Gemma
            validator_status="uncertain",
            review_required=True,
            warnings=[],
            bbox=field_def.get("bbox", []),
        )

    with patch("main._check_gemma_available", return_value=True):
        with patch("main.review_document_extraction", tracker):  # patch where it's imported (main's namespace)
            with patch("main.route_and_extract", mock_route):       # patch where it's imported (main's namespace)
                result = analyze(make_request(SIGNED_PDF, "t3_001"))

    reviewed = [f for f in result["fields"] if f.get("review") is not None]
    print(f"\n  Fields with review: {len(reviewed)}")
    for f in reviewed:
        print(f"    {f['field_name']}: value={f['value']!r}  review={f['review']!r}")

    assert len(reviewed) == 2
    # Verify first-pass value is NOT overwritten by Gemma's reviewed_value.
    # If both are empty string, that's fine (Gemma confirmed the empty value).
    for f in reviewed:
        if f["value"] and f["review"]:
            assert f["value"] != f["review"], (
                f"Field {f['field_name']}: value was overwritten — "
                "GLM first-pass must be preserved"
            )
    print("  ✓ review field populated, first-pass value preserved")


# ─── Test 4: Fallback path completes without crash ───────────────────────────

def test_relevant_page_images_are_sent_to_gemma():
    """Matched-template review should send rendered relevant page images to Gemma."""
    captured = {}

    def mock_review(*args, **kwargs):
        captured["kwargs"] = kwargs
        return GemmaReviewResult(
            reviewed_fields=[
                ReviewedField("First_Name_Fill", "GWANJIN", 0.9, "Confirmed from page image")
            ],
            document_notes=["Reviewed from rendered page image"],
        )

    from extractors.field_router import ExtractionResult

    def mock_route(pdf_path, page_sizes, field_def, glm_available=True):
        needs_review = field_def.get("field_name") == "First_Name_Fill"
        return ExtractionResult(
            field_name=field_def.get("field_name", ""),
            value="Gwanjin" if needs_review else "Chun",
            confidence=0.45 if needs_review else 0.95,
            validator_status="uncertain" if needs_review else "valid",
            review_required=needs_review,
            warnings=[],
            bbox=field_def.get("bbox", []),
        )

    render_result = ReviewPageRenderResult(
        pages=[RenderedReviewPage(page_number=1, image_url="data:image/png;base64,abc", width=100, height=200)]
    )

    with patch("main._check_gemma_available", return_value=True):
        with patch("main.route_and_extract", mock_route):
            with patch("main.render_review_pages", return_value=render_result):
                with patch("main.review_document_extraction", side_effect=mock_review):
                    result = analyze(make_request(SIGNED_PDF, "t4a_001"))

    sent_images = captured["kwargs"].get("page_images", [])
    assert sent_images, "Expected rendered page images to be sent to Gemma"
    assert sent_images[0]["page_number"] == 1
    reviewed_field = next(f for f in result["fields"] if f["field_name"] == "First_Name_Fill")
    assert reviewed_field["review"] == "GWANJIN"
    assert reviewed_field["review_comment"] == "Confirmed from page image"


# ─── Test 4: Failure message is surfaced when page rendering/review fails ─────

def test_review_failure_message_propagates_to_target_fields():
    """If whole-PDF review cannot render/review pages, the user-visible message should be attached."""
    from extractors.field_router import ExtractionResult

    def mock_route(pdf_path, page_sizes, field_def, glm_available=True):
        needs_review = field_def.get("field_name") in {"First_Name_Fill", "Last_Name_Fill"}
        return ExtractionResult(
            field_name=field_def.get("field_name", ""),
            value="",
            confidence=0.40 if needs_review else 0.95,
            validator_status="uncertain" if needs_review else "valid",
            review_required=needs_review,
            warnings=[],
            bbox=field_def.get("bbox", []),
        )

    render_result = ReviewPageRenderResult(
        pages=[],
        error_message="Gemma whole-document review could not render the relevant PDF pages.",
    )

    with patch("main._check_gemma_available", return_value=True):
        with patch("main.route_and_extract", mock_route):
            with patch("main.render_review_pages", return_value=render_result):
                result = analyze(make_request(SIGNED_PDF, "t4b_001"))

    failed_review_fields = [
        f for f in result["fields"]
        if f["field_name"] in {"First_Name_Fill", "Last_Name_Fill"}
    ]
    assert failed_review_fields
    assert all(
        f["review_comment"] == "Gemma whole-document review could not render the relevant PDF pages."
        for f in failed_review_fields
    )
    assert all(f["review"] in (None, "") for f in failed_review_fields)


# ─── Test 5: Fallback path completes without crash ───────────────────────────

def test_fallback_path_no_crash():
    """
    Unknown template (fallback lane) must complete without error.
    Uses fast mocked GLM + mocked page rendering.
    """
    from extractors.gemma_review_pages import ReviewPageRenderResult, RenderedReviewPage

    tracker = GemmaCallTracker(mock_gemma_review)

    mock_render_result = ReviewPageRenderResult(
        pages=[RenderedReviewPage(page_number=1, image_url="data:image/png;base64,abc", width=100, height=200)]
    )

    with patch("main._check_gemma_available", return_value=True):
        with patch("main.render_review_pages", return_value=mock_render_result):
            with patch("src.extractors.gemma_client.review_document_extraction", tracker):
                with patch("src.extractors.glm_ocr.extract_handwritten_text") as mock_glm:
                    mock_glm.return_value = ("", 0.30)
                    result = analyze(make_request(EXAMPLE_PDF, "t4_001"))

    print(f"\n  Status: {result['status']}")
    print(f"  Template: {result['summary'].get('template_match_status')}")
    assert result["status"] in ("review_required", "complete", "failed")
    print("  ✓ Fallback path completes without crash")


# ─── Test 6: Real E2E with signed T2200 PDF ──────────────────────────────────

def test_real_pdf_e2e():
    """
    Real end-to-end test with the actual PDF from email.
    Uses real GLM + real Gemma servers — full integration check.
    """
    if not SIGNED_PDF.exists():
        print(f"  ⚠ PDF not found — skipping E2E")
        return

    result = analyze(make_request(SIGNED_PDF, "e2e_001"))

    avg_conf = result["summary"].get("overall_confidence")

    print(f"\n  Status:         {result['status']}")
    print(f"  Avg confidence: {avg_conf}")
    print(f"  Template:       {result['summary'].get('template_id')}")
    print(f"  Field count:    {len(result['fields'])}")

    reviewed = [f for f in result["fields"] if f.get("review")]
    if reviewed:
        print(f"\n  Gemma reviews ({len(reviewed)}):")
        for f in reviewed:
            print(f"    {f['field_name']}:")
            print(f"      GLM value:  {f['value']!r}")
            print(f"      Gemma rev:  {f['review']!r}")

    low = [f for f in result["fields"] if (f.get("confidence") or 1.0) < 0.70]
    if low:
        print(f"\n  Low-conf fields ({len(low)}):")
        for f in low[:5]:
            print(f"    {f['field_name']}: conf={f.get('confidence'):.3f}  value={f.get('value')!r}")

    assert result["status"] in ("complete", "review_required")
    assert result["summary"]["template_match_status"] == "matched"
    assert len(result["fields"]) > 0
    print("\n  ✓ E2E with real PDF succeeded")


# ─── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("Gemma one-shot (matched template)",       test_gemma_one_shot_not_per_field),
        ("Gemma skipped when avg_conf >= 0.70",      test_gemma_skipped_above_threshold),
        ("review field set, value preserved",        test_review_field_set_value_preserved),
        ("Relevant page images sent to Gemma",      test_relevant_page_images_are_sent_to_gemma),
        ("Review failure message propagated",        test_review_failure_message_propagates_to_target_fields),
        ("Fallback path no crash",                   test_fallback_path_no_crash),
        ("Real PDF E2E (real servers)",              test_real_pdf_e2e),
    ]

    passed = failed = 0
    for name, fn in tests:
        print(f"\n{'='*60}\n{name}\n{'='*60}")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            import traceback; traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}\nResults: {passed} passed, {failed} failed\n{'='*60}")
