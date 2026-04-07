# Roadmap — 고도화 계획

> cycle-2026-04-06-002에서 P0~P2 7개 티켓 전부 완료.

---

## ✅ 완료된 티켓 (cycle-2026-04-06-002)

| ID | 제목 | 상태 |
|---|---|---|
| TICKET-001 | pytest 테스트 기반 구축 | ✅ 45 tests passing |
| TICKET-002 | requirements.txt 정비 | ✅ |
| TICKET-003 | 입력 검증 강화 | ✅ |
| TICKET-004 | 에러 응답 체계화 | ✅ |
| TICKET-005 | CSS 외부화 | ✅ |
| TICKET-006 | HWP 파서 지원 완성 | ✅ |
| TICKET-007 | 대시보드 통합 현황판 | ✅ |

---

## 다음 사이클 후보 (P2~P3)

### TICKET-008: 의존성 버전 상한 명시
- **SCOPE:** `requirements.txt`
- **사유:** cycle-2 lessons — starlette/fastapi 버전 호환성 이슈 재발 방지
- **내용:** `fastapi>=0.110,<0.115`, `starlette<0.40` 등 상한 추가

### TICKET-009: 실제 파일 업로드 통합 테스트
- **SCOPE:** `__tests__/test_document_upload.py`
- **사유:** 현재는 검증 로직만 테스트. 실제 PDF/DOCX 업로드 → 파싱 → 매핑 E2E 미검증
- **내용:** 샘플 PDF fixture, 업로드 → get_document → parse → sections 확인

### TICKET-010: 매핑 자동화 정밀도 개선
- **SCOPE:** `app/services/mapping_service.py`, `app/services/fulfillment_assessor.py`
- **사유:** 현재 키워드 기반만 → 임베딩 기반 보완 필요
- **COMPLEXITY:** high

### TICKET-011: MCP 서버 통합 대시보드
- **SCOPE:** `mcp_server/`, `app/routes/`
- **사유:** MCP 서버가 독립 실행되어 웹 UI와 분리되어 있음
- **내용:** MCP 툴 호출 이력 노출, Claude 세션 연동 상태 표시

### TICKET-012: 다국어/번역 준비
- **SCOPE:** 전체 템플릿
- **사유:** 영어/일본어 해외 파트너 사용 가능성
- **COMPLEXITY:** medium

---

## 구조적 개선 제안 (50 cycles 후 재평가)

- Self-Evolution Engine 활성화 (현재 `[layers.evolution].enabled = false`)
- Visual Perception Layer 활성화 — 사용자 피드백 기반 UI 자동 조정
- env-profiles 추가 — 배포 자동화 (현재 수동)
