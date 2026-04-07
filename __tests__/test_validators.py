"""app.validators 단위 테스트."""
from __future__ import annotations

import pytest

from app.validators import (
    ValidationError,
    validate_doc_type,
    validate_doc_status,
    validate_file_upload,
    validate_item_code,
    validate_coverage_level,
    validate_fulfillment_type,
    MAX_FILE_SIZE_BYTES,
)


class TestDocType:
    def test_valid(self):
        assert validate_doc_type("정책서") == "정책서"

    def test_empty(self):
        with pytest.raises(ValidationError):
            validate_doc_type("")

    def test_invalid(self):
        with pytest.raises(ValidationError):
            validate_doc_type("랜덤문서")


class TestDocStatus:
    def test_valid(self):
        for s in ("draft", "active", "expired", "superseded", "archived"):
            assert validate_doc_status(s) == s

    def test_invalid(self):
        with pytest.raises(ValidationError):
            validate_doc_status("unknown")


class TestFileUpload:
    def test_valid_pdf(self):
        validate_file_upload("doc.pdf", 1024)

    def test_valid_docx(self):
        validate_file_upload("정책.docx", 5000)

    def test_empty_name(self):
        with pytest.raises(ValidationError):
            validate_file_upload("", 1024)

    def test_empty_file(self):
        with pytest.raises(ValidationError):
            validate_file_upload("a.pdf", 0)

    def test_too_large(self):
        with pytest.raises(ValidationError):
            validate_file_upload("big.pdf", MAX_FILE_SIZE_BYTES + 1)

    def test_disallowed_ext(self):
        with pytest.raises(ValidationError):
            validate_file_upload("malicious.exe", 1024)


class TestItemCode:
    def test_valid(self):
        assert validate_item_code("1.1.1") == "1.1.1"
        assert validate_item_code("2.10.3") == "2.10.3"

    def test_wrong_format(self):
        for bad in ("1.1", "1.1.1.1", "A.1.1", "", "1-1-1"):
            with pytest.raises(ValidationError):
                validate_item_code(bad)


class TestCoverageLevel:
    def test_valid(self):
        for v in ("full", "partial", "reference"):
            assert validate_coverage_level(v) == v

    def test_invalid(self):
        with pytest.raises(ValidationError):
            validate_coverage_level("none")


class TestFulfillmentType:
    def test_valid(self):
        for v in ("document", "system", "mixed"):
            assert validate_fulfillment_type(v) == v

    def test_invalid(self):
        with pytest.raises(ValidationError):
            validate_fulfillment_type("manual")
