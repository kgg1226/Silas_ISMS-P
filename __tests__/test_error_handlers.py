"""전역 예외 핸들러 검증 (TICKET-004)."""
from __future__ import annotations


def test_404_renders_error_template(test_client):
    resp = test_client.get("/item/ZZ.99.99")
    assert resp.status_code == 404
    # error.html 템플릿이 렌더링됐는지 (status_code 숫자가 본문에 있어야 함)
    assert "404" in resp.text
    assert "항목" in resp.text or "찾을 수 없" in resp.text


def test_document_not_found_returns_404(test_client):
    resp = test_client.get("/documents/99999")
    assert resp.status_code == 404
    assert "404" in resp.text


def test_nonexistent_route_404(test_client):
    resp = test_client.get("/this-does-not-exist")
    assert resp.status_code == 404
