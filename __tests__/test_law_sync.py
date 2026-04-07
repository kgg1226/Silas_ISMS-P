"""law_sync 단위 테스트 — 외부 API 호출 없이 로직 검증."""
from __future__ import annotations

from unittest.mock import patch


def test_law_name_aliases_loaded():
    from app.law_sync import LAW_NAME_ALIASES
    assert "정보통신망 이용촉진 및 정보보호 등에 관한 법률" in LAW_NAME_ALIASES
    assert LAW_NAME_ALIASES["정보통신망 이용촉진 및 정보보호 등에 관한 법률"] == "정보통신망법"


def test_tracked_laws_has_targets():
    from app.law_sync import TRACKED_LAWS
    assert len(TRACKED_LAWS) >= 10
    for entry in TRACKED_LAWS:
        assert "name" in entry
        assert "target" in entry
        assert entry["target"] in ("law", "admrul")


def test_ensure_law_tables_idempotent(initialized_db):
    from app.law_sync import ensure_law_tables
    # 여러 번 호출해도 에러 없어야 함
    ensure_law_tables()
    ensure_law_tables()


def test_init_tracked_laws_populates(initialized_db):
    from app.law_sync import init_tracked_laws, get_law_status_summary, TRACKED_LAWS
    init_tracked_laws()
    summary = get_law_status_summary()
    assert summary["total"] >= len(TRACKED_LAWS)


def test_sync_single_law_without_api_key(initialized_db, monkeypatch):
    """API 키 없이 호출 시 에러 상태로 반환되어야 함 (500 X)."""
    monkeypatch.delenv("LAW_API_KEY", raising=False)
    from app.law_sync import sync_single_law, init_tracked_laws
    init_tracked_laws()
    result = sync_single_law("개인정보 보호법", target="law")
    assert result["status"] == "error"
    assert "LAW_API_KEY" in result["message"] or "오류" in result["message"]
