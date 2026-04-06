# Roadmap — 고도화 계획

> Governor가 planner 분석 기반으로 생성. 2026-04-06.

---

## P0 — 즉시 (안정성/신뢰성)

### TICKET-001: pytest 테스트 기반 구축
- **SCOPE:** `__tests__/`, `requirements.txt`
- **COMPLEXITY:** medium
- **내용:** pytest 환경 세팅, DB 스키마 검증, 주요 엔드포인트 smoke test, law_sync 단위 테스트
- **사유:** 하드 룰 #1(테스트 스냅샷)의 전제조건

### TICKET-002: requirements.txt 정비
- **SCOPE:** `requirements.txt`
- **COMPLEXITY:** low
- **내용:** pytest/pytest-asyncio/httpx 추가, HWP 의존성 확인

---

## P1 — 단기 (기능 완성도)

### TICKET-003: 입력 검증 강화
- **SCOPE:** `app/routes/*.py`
- **COMPLEXITY:** low
- **내용:** doc_type 화이트리스트, item_code 형식, 파일 크기/확장자 검증

### TICKET-004: 에러 응답 체계화
- **SCOPE:** `app/main.py`, `app/routes/*.py`, `app/templates/`
- **COMPLEXITY:** low
- **내용:** exception_handler 등록, error.html 템플릿, DB 연결 폴백

---

## P2 — 중기 (운영 품질)

### TICKET-005: CSS 외부화
- **SCOPE:** `app/static/`, `app/templates/base.html`
- **COMPLEXITY:** low

### TICKET-006: HWP 파서 지원 완성
- **SCOPE:** `app/services/parser_service.py`, `requirements.txt`
- **COMPLEXITY:** medium

### TICKET-007: 대시보드 통합 현황판
- **SCOPE:** `app/main.py`, `app/templates/dashboard.html`
- **COMPLEXITY:** medium

---

## 실행 순서

```
TICKET-002 → TICKET-001 → TICKET-003 + TICKET-004 (병렬) → TICKET-005 + TICKET-006 + TICKET-007 (병렬)
```
