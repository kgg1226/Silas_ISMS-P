"""
Tests for app/i18n.py — lightweight i18n foundation.

Covers:
- Korean default translations
- English fallback when key exists in en
- Fallback to Korean when en value is absent/empty
- Unknown locale falls back to Korean
- Missing key returns the key itself (never crashes)
"""

from __future__ import annotations

import pytest

from app.i18n import get_text, DEFAULT_LOCALE


# ---------------------------------------------------------------------------
# test_get_text_korean_default
# ---------------------------------------------------------------------------

class TestGetTextKoreanDefault:
    """get_text returns Korean strings when locale is "ko" (the default)."""

    def test_default_locale_is_ko(self):
        assert DEFAULT_LOCALE == "ko"

    def test_nav_dashboard_ko(self):
        assert get_text("nav.dashboard") == "대시보드"

    def test_nav_documents_ko(self):
        assert get_text("nav.documents") == "문서 관리"

    def test_nav_mappings_ko(self):
        assert get_text("nav.mappings") == "매핑 관리"

    def test_nav_gap_ko(self):
        assert get_text("nav.gap") == "갭 분석"

    def test_nav_laws_ko(self):
        assert get_text("nav.laws") == "법령 관리"

    def test_btn_search_ko(self):
        assert get_text("btn.search") == "검색"

    def test_btn_upload_ko(self):
        assert get_text("btn.upload") == "업로드"

    def test_btn_sync_ko(self):
        assert get_text("btn.sync") == "동기화"

    def test_status_ok_ko(self):
        assert get_text("status.ok") == "정상"

    def test_status_warn_ko(self):
        assert get_text("status.warn") == "주의"

    def test_explicit_ko_locale_same_as_default(self):
        assert get_text("nav.dashboard", locale="ko") == get_text("nav.dashboard")


# ---------------------------------------------------------------------------
# test_get_text_english_fallback
# ---------------------------------------------------------------------------

class TestGetTextEnglishFallback:
    """get_text returns English strings for locale="en"."""

    def test_nav_dashboard_en(self):
        assert get_text("nav.dashboard", locale="en") == "Dashboard"

    def test_nav_documents_en(self):
        assert get_text("nav.documents", locale="en") == "Documents"

    def test_nav_mappings_en(self):
        assert get_text("nav.mappings", locale="en") == "Mappings"

    def test_nav_gap_en(self):
        assert get_text("nav.gap", locale="en") == "Gap Analysis"

    def test_nav_laws_en(self):
        assert get_text("nav.laws", locale="en") == "Laws"

    def test_btn_search_en(self):
        assert get_text("btn.search", locale="en") == "Search"

    def test_status_ok_en(self):
        assert get_text("status.ok", locale="en") == "OK"

    def test_bcp47_locale_normalised(self):
        """Locale tags like "en-US" are normalised to "en"."""
        assert get_text("nav.dashboard", locale="en-US") == "Dashboard"

    def test_japanese_locale(self):
        assert get_text("nav.dashboard", locale="ja") == "ダッシュボード"


# ---------------------------------------------------------------------------
# test_get_text_missing_key_returns_key
# ---------------------------------------------------------------------------

class TestGetTextMissingKeyReturnsKey:
    """get_text never raises; unknown keys are returned verbatim."""

    def test_unknown_key_ko(self):
        result = get_text("nonexistent.key", locale="ko")
        assert result == "nonexistent.key"

    def test_unknown_key_en(self):
        result = get_text("no.such.thing", locale="en")
        assert result == "no.such.thing"

    def test_unknown_key_unknown_locale(self):
        """Completely unknown locale + key → key itself."""
        result = get_text("totally.missing", locale="fr")
        assert result == "totally.missing"

    def test_unknown_locale_known_key_falls_back_to_korean(self):
        """Unknown locale with a key that exists in Korean → Korean value."""
        result = get_text("nav.dashboard", locale="fr")
        assert result == "대시보드"

    def test_empty_key_returns_empty_key(self):
        """Empty-string key is returned as-is."""
        result = get_text("")
        assert result == ""

    def test_no_exception_on_none_like_empty_locale(self):
        """Empty locale string is treated as default (ko)."""
        result = get_text("nav.dashboard", locale="")
        # Empty string splits to [""], no locale match → falls back to ko
        assert result == "대시보드"
