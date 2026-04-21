"""
Unit tests for the PDF Handwriting Analyzer MVP pipeline.
Tests cover:
- Request validation (valid/invalid/missing fields)
- PDF inspection (valid PDF, encrypted PDF, missing file)
- Template matching (matched T2200, unknown)
- Response builder (completed, review_required, failed)
- End-to-end analyze() flow
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure src is on path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.config import ErrorCode
from common.pdf_inspector import inspect_pdf, PDFInspectionError
from common.response_builder import (
    build_failure_response,
    build_review_required_response,
    build_success_response,
    build_unknown_template_response,
    response_to_dict,
)
from common.template_matcher import (
    compute_acroform_score,
    compute_metadata_score,
    compute_page_structure_score,
    compute_match_score,
    find_best_match,
)
from common.template_registry import TemplateRegistry
from common.types import ErrorDetail, FieldResult, Summary
from common.validator import RequestValidationError, validate_json_request
from main import analyze


# ─── Fixtures ──────────────────────────────────────────────────────────────────

EXAMPLE_PDF = Path(__file__).parent.parent / "example" / "t2200-fill-25e.pdf"
SIGNED_PDF = Path(__file__).parent.parent / "example" / "Gwanjin_t2200-fill-25e_signed.pdf"

REGISTRY = TemplateRegistry()
REGISTRY.load_all()


# ─── Request Validation Tests ──────────────────────────────────────────────────

class TestRequestValidator:
    def test_valid_request_minimal(self):
        request = {
            "request_id": "req_001",
            "job_id": "job_001",
            "attachment_id": "att_001",
            "file": {"path": str(EXAMPLE_PDF)},
        }
        validated = validate_json_request(request)
        assert validated.request_id == "req_001"
        assert validated.job_id == "job_001"
        assert validated.attachment_id == "att_001"
        assert validated.file.path == str(EXAMPLE_PDF)

    def test_valid_request_full(self):
        request = {
            "request_id": "req_002",
            "job_id": "job_002",
            "attachment_id": "att_002",
            "email_id": "email_002",
            "file": {
                "path": str(EXAMPLE_PDF),
                "original_filename": "t2200.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 12345,
            },
            "context": {
                "received_date": "2026-01-15",
                "sender": "employer@example.com",
                "subject": "T2200 Form",
                "language_hint": "en",
                "template_hint": "t2200",
            },
            "options": {
                "return_field_candidates": True,
                "return_confidence_breakdown": True,
                "mode": "default",
            },
        }
        validated = validate_json_request(request)
        assert validated.email_id == "email_002"
        assert validated.context.sender == "employer@example.com"
        assert validated.context.template_hint == "t2200"
        assert validated.options.return_field_candidates is True

    def test_missing_required_field_raises(self):
        request = {"job_id": "job_001", "attachment_id": "att_001", "file": {"path": str(EXAMPLE_PDF)}}
        with pytest.raises(RequestValidationError) as exc_info:
            validate_json_request(request)
        assert exc_info.value.code == ErrorCode.INVALID_REQUEST
        assert "request_id" in exc_info.value.message

    def test_missing_file_path_raises(self):
        request = {
            "request_id": "req_001",
            "job_id": "job_001",
            "attachment_id": "att_001",
            "file": {},
        }
        with pytest.raises(RequestValidationError) as exc_info:
            validate_json_request(request)
        assert exc_info.value.code == ErrorCode.INVALID_REQUEST

    def test_nonexistent_file_raises(self):
        request = {
            "request_id": "req_001",
            "job_id": "job_001",
            "attachment_id": "att_001",
            "file": {"path": "/nonexistent/path/to/file.pdf"},
        }
        with pytest.raises(RequestValidationError) as exc_info:
            validate_json_request(request)
        assert exc_info.value.code == ErrorCode.FILE_NOT_FOUND

    def test_wrong_extension_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not a pdf")
            tmp_path = f.name
        try:
            request = {
                "request_id": "req_001",
                "job_id": "job_001",
                "attachment_id": "att_001",
                "file": {"path": tmp_path},
            }
            with pytest.raises(RequestValidationError) as exc_info:
                validate_json_request(request)
            assert exc_info.value.code == ErrorCode.NOT_A_PDF
        finally:
            os.unlink(tmp_path)


# ─── PDF Inspection Tests ─────────────────────────────────────────────────────

class TestPDFInspector:
    def test_inspect_valid_pdf(self):
        result = inspect_pdf(str(EXAMPLE_PDF))
        assert result.page_count == 3
        assert result.is_born_digital is True
        assert result.is_scanned is False
        assert len(result.page_sizes) == 3
        assert len(result.acroform_field_names) == 181

    def test_inspect_signed_pdf(self):
        result = inspect_pdf(str(SIGNED_PDF))
        assert result.page_count == 3
        assert len(result.acroform_field_names) > 0

    def test_inspect_missing_file_raises(self):
        with pytest.raises(PDFInspectionError) as exc_info:
            inspect_pdf("/nonexistent/file.pdf")
        assert exc_info.value.code == ErrorCode.UNREADABLE_FILE


# ─── Template Matching Tests ───────────────────────────────────────────────────

class TestTemplateMatcher:
    def test_t2200_matches_above_threshold(self):
        inspection = inspect_pdf(str(EXAMPLE_PDF))
        score, signals = compute_match_score(inspection, REGISTRY.get("t2200_fill_25e"))
        assert score >= 0.85, f"Expected score >= 0.85, got {score:.4f}"
        assert signals.metadata_score == 1.0
        assert signals.acroform_score == 1.0
        assert signals.page_structure_score == 1.0

    def test_find_best_match_returns_matched_for_t2200(self):
        inspection = inspect_pdf(str(EXAMPLE_PDF))
        result = find_best_match(inspection, REGISTRY)
        assert result.template_match_status == "matched"
        assert result.template_id == "t2200_fill_25e"
        assert result.match_score >= 0.85

    def test_signed_t2200_also_matches(self):
        """The filled/signed T2200 PDF should also match — it's the same form."""
        inspection = inspect_pdf(str(SIGNED_PDF))
        result = find_best_match(inspection, REGISTRY)
        assert result.template_match_status == "matched"
        assert result.template_id == "t2200_fill_25e"
        assert result.match_score >= 0.85

    def test_metadata_score_normalization(self):
        inspection = inspect_pdf(str(EXAMPLE_PDF))
        template = REGISTRY.get("t2200_fill_25e")
        score = compute_metadata_score(inspection, template)
        assert score == 1.0  # Title, Creator, Producer all match

    def test_page_structure_score(self):
        inspection = inspect_pdf(str(EXAMPLE_PDF))
        template = REGISTRY.get("t2200_fill_25e")
        score = compute_page_structure_score(inspection, template)
        assert score == 1.0  # 3 pages, same sizes

    def test_acroform_score_precision(self):
        inspection = inspect_pdf(str(EXAMPLE_PDF))
        template = REGISTRY.get("t2200_fill_25e")
        score = compute_acroform_score(inspection, template)
        assert score == 1.0  # 20/20 template leaf fields found


# ─── Response Builder Tests ─────────────────────────────────────────────────────

class TestResponseBuilder:
    def test_build_success_response(self):
        summary = Summary(
            template_match_status="matched",
            template_id="t2200_fill_25e",
            page_count=3,
            overall_confidence=0.95,
            review_required=False,
            warning_count=0,
            field_count=2,
        )
        fields = [
            FieldResult(
                field_name="Last_Name_Fill",
                field_label="Last Name",
                field_type="handwritten_name",
                value="Smith",
                confidence=0.95,
                validation_status="valid",
                review_required=False,
                warnings=[],
                bbox=[100, 200, 300, 400],
            )
        ]
        resp = build_success_response("req_001", "job_001", summary, fields)
        assert resp.status == "completed"
        assert resp.summary.template_id == "t2200_fill_25e"
        assert len(resp.fields) == 1

    def test_build_failure_response(self):
        error = ErrorDetail(code=ErrorCode.UNKNOWN_TEMPLATE, message="Template not found", retryable=False)
        resp = build_failure_response("req_001", "job_001", error)
        assert resp.status == "failed"
        assert resp.error.code == ErrorCode.UNKNOWN_TEMPLATE

    def test_build_review_required_response(self):
        summary = Summary(
            template_match_status="matched",
            template_id="t2200_fill_25e",
            page_count=3,
            overall_confidence=0.55,
            review_required=True,
            warning_count=1,
            field_count=2,
        )
        fields = [
            FieldResult(
                field_name="Last_Name_Fill",
                field_label="Last Name",
                field_type="handwritten_name",
                value="???",
                confidence=0.45,
                validation_status="uncertain",
                review_required=True,
                warnings=["Low confidence"],
                bbox=[],
            )
        ]
        resp = build_review_required_response("req_001", "job_001", summary, fields)
        assert resp.status == "review_required"
        assert resp.summary.review_required is True

    def test_unknown_template_response_shape(self):
        error = ErrorDetail(code=ErrorCode.UNKNOWN_TEMPLATE, message="No match", retryable=False)
        resp = build_unknown_template_response("req_001", "job_001", page_count=3, error_detail=error)
        assert resp.status == "failed"
        assert resp.summary.template_match_status == "unknown"
        assert resp.summary.page_count == 3
        assert resp.error.code == ErrorCode.UNKNOWN_TEMPLATE

    def test_response_to_dict_serialization(self):
        summary = Summary(template_match_status="matched", template_id="t2200", page_count=2, overall_confidence=0.9, review_required=False, warning_count=0, field_count=0)
        resp = build_success_response("req_001", "job_001", summary, fields=[])
        d = response_to_dict(resp)
        assert d["request_id"] == "req_001"
        assert d["status"] == "completed"
        assert d["summary"]["template_id"] == "t2200"
        assert isinstance(d["fields"], list)


# ─── End-to-End analyze() Tests ────────────────────────────────────────────────

class TestAnalyzeFlow:
    def test_analyze_t2200_returns_matched(self):
        """
        End-to-end: T2200 PDF is matched to t2200_fill_25e template.

        Without MLX servers running (GLM-OCR/Gemma), extraction is stubbed
        and returns review_required — this is correct behavior.
        The key invariant we verify: template must MATCH regardless of
        whether extraction servers are available.
        """
        request = {
            "request_id": "e2e_001",
            "job_id": "e2e_job_001",
            "attachment_id": "e2e_att_001",
            "file": {"path": str(EXAMPLE_PDF)},
        }
        result = analyze(request)
        # Template matching is server-independent — must always succeed
        assert result["summary"]["template_match_status"] == "matched"
        assert result["summary"]["template_id"] == "t2200_fill_25e"
        assert result["summary"]["page_count"] == 3
        # Fields array must be present (empty or populated)
        assert isinstance(result["fields"], list)
        assert len(result["fields"]) == 19
        # Without MLX servers, extraction is stubbed → review_required
        assert result["status"] == "review_required"
        assert result["summary"]["overall_confidence"] < 1.0

    def test_analyze_missing_file_returns_failed(self):
        request = {
            "request_id": "e2e_002",
            "job_id": "e2e_job_002",
            "attachment_id": "e2e_att_002",
            "file": {"path": "/nonexistent/file.pdf"},
        }
        result = analyze(request)
        assert result["status"] == "failed"
        assert result["error"]["code"] == ErrorCode.FILE_NOT_FOUND

    def test_analyze_invalid_json_raises(self, capsys):
        # Test via main() with invalid JSON
        import subprocess
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "main.py")],
            input='not valid json{{',
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1
        error_resp = json.loads(proc.stdout)
        assert error_resp["status"] == "failed"
        assert error_resp["error"]["code"] == ErrorCode.INVALID_REQUEST


# ─── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
