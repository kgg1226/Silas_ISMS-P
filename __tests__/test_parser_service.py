"""parser_service의 파서 가용성 체크 (TICKET-006)."""
from __future__ import annotations


def test_supported_extensions_include_hwp():
    from app.services.parser_service import get_supported_extensions
    ext = get_supported_extensions()
    assert ".hwp" in ext
    assert ".hwpx" in ext
    assert ".pdf" in ext
    assert ".docx" in ext


def test_is_parser_available_pdf():
    from app.services.parser_service import is_parser_available
    ok, msg = is_parser_available(".pdf")
    # pdfplumber가 설치되어 있다면 True
    assert isinstance(ok, bool)
    if not ok:
        assert "pdfplumber" in msg


def test_is_parser_available_unknown():
    from app.services.parser_service import is_parser_available
    ok, msg = is_parser_available(".exe")
    assert ok is False
    assert "지원" in msg or "exe" in msg


def test_is_parser_available_hwpx_uses_stdlib():
    """HWPX는 zipfile 표준 라이브러리만 쓰므로 항상 True여야 함."""
    from app.services.parser_service import is_parser_available
    ok, _ = is_parser_available(".hwpx")
    assert ok is True
