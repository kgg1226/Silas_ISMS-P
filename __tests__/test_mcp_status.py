"""MCP 서버 상태 엔드포인트 테스트."""
from __future__ import annotations

import pytest


def test_mcp_status_endpoint(test_client):
    """GET /mcp/status — 200 응답 및 tools 목록 포함 확인."""
    resp = test_client.get("/mcp/status")
    assert resp.status_code == 200

    data = resp.json()
    assert "tools" in data
    assert isinstance(data["tools"], list)
    assert len(data["tools"]) > 0

    # 각 도구 항목에 name 필드 포함 확인
    for tool in data["tools"]:
        assert "name" in tool
        assert "description" in tool

    # 핵심 도구 포함 확인
    tool_names = [t["name"] for t in data["tools"]]
    assert "search_requirements" in tool_names
    assert "get_requirement_detail" in tool_names
    assert "generate_evidence" in tool_names

    # tool_count 일치 확인
    assert data["tool_count"] == len(data["tools"])

    # server 정보 확인
    assert "server" in data
    assert data["server"]["name"] == "isms-p"


def test_dashboard_shows_mcp(test_client):
    """GET / — 대시보드에 MCP 텍스트 및 도구 목록 포함 확인."""
    resp = test_client.get("/")
    assert resp.status_code == 200
    assert "MCP" in resp.text
    # 도구 카드 제목 확인
    assert "MCP 서버 도구" in resp.text
    # 최소 하나의 도구 이름이 표시되는지 확인
    assert "search_requirements" in resp.text
