"""isms_sync 단위 테스트."""
from __future__ import annotations


def test_ensure_isms_sync_tables(initialized_db):
    from app.isms_sync import ensure_isms_sync_tables
    ensure_isms_sync_tables()
    ensure_isms_sync_tables()  # idempotent


def test_get_isms_sync_status_empty(initialized_db):
    from app.isms_sync import get_isms_sync_status
    status = get_isms_sync_status()
    assert "version" in status
    assert status["version"]["current"]  # CURRENT_GUIDE_VERSION
    assert "reference_sources" in status


def test_compare_item_invalid_field(initialized_db):
    from app.isms_sync import compare_item
    r = compare_item("1.1.1", "not_a_field", "new value")
    assert r["changed"] is False
    assert "유효" in r["diff_summary"]


def test_reference_sources_are_untrusted():
    from app.isms_sync import REFERENCE_SOURCES
    for src in REFERENCE_SOURCES:
        assert src.get("trusted") is False, "비공식 소스는 trusted=False여야 함"
