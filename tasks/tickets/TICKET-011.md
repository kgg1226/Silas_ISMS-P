# TICKET-011: MCP 서버 통합 대시보드

- **Status:** in_progress
- **Priority:** P3
- **Scope:** `app/routes/mcp_status.py`, `app/templates/mcp_dashboard.html`

## 문제

현재 `/mcp/status`는 JSON API만 제공. 웹 UI에서 MCP 도구 목록 및 서버 정보를
직관적으로 확인할 방법이 없음.

## 구현

1. `GET /mcp/dashboard` HTML 라우트 추가
2. `app/templates/mcp_dashboard.html` 템플릿 생성
