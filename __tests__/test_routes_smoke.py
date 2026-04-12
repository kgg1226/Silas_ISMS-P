"""핵심 엔드포인트 smoke test — 200/303 응답 확인."""
from __future__ import annotations

import pytest


def test_dashboard_loads(test_client):
    resp = test_client.get("/")
    assert resp.status_code == 200


def test_dashboard_has_overview_section(test_client):
    """TICKET-007: 통합 현황판 표시 확인."""
    resp = test_client.get("/")
    assert resp.status_code == 200
    # overview 섹션 키워드 (전체 인증기준, 커버리지)
    assert "전체 현황" in resp.text
    assert "커버리지" in resp.text


def test_laws_page_loads(test_client):
    resp = test_client.get("/laws")
    assert resp.status_code == 200
    assert "법령" in resp.text or "law" in resp.text.lower()


def test_documents_page_loads(test_client):
    resp = test_client.get("/documents")
    assert resp.status_code == 200


def test_gap_page_loads(test_client):
    resp = test_client.get("/gap")
    assert resp.status_code == 200


def test_mappings_page_loads(test_client):
    resp = test_client.get("/mappings")
    assert resp.status_code == 200


def test_laws_sync_post_safe(test_client, monkeypatch):
    """API 키 없이 POST해도 500 아닌 303으로 응답해야 함 (에러 핸들링)."""
    monkeypatch.delenv("LAW_API_KEY", raising=False)
    resp = test_client.post("/laws/sync", follow_redirects=False)
    assert resp.status_code == 303
    # 플래시 쿼리 파라미터 포함
    loc = resp.headers.get("location", "")
    assert "/laws" in loc
    assert "flash" in loc


def test_laws_isms_check_post_safe(test_client):
    """KISA 조회 실패해도 500 X."""
    resp = test_client.post("/laws/isms-check", follow_redirects=False)
    assert resp.status_code == 303


def test_nonexistent_item_returns_404(test_client):
    resp = test_client.get("/item/ZZ.99.99")
    assert resp.status_code == 404


def test_mcp_status_returns_json(test_client):
    """GET /mcp/status 는 도구 목록 JSON을 반환해야 한다."""
    resp = test_client.get("/mcp/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data
    assert data["tool_count"] == len(data["tools"])


def test_mcp_dashboard_loads(test_client):
    """GET /mcp/dashboard 는 HTML 페이지를 반환하고 도구 목록이 포함되어야 한다."""
    resp = test_client.get("/mcp/dashboard")
    assert resp.status_code == 200
    assert "MCP" in resp.text
    assert "search_requirements" in resp.text
