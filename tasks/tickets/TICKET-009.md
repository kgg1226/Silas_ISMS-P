# TICKET-009: 실제 파일 업로드 통합 테스트

- **Status:** in_progress
- **Priority:** P2
- **Scope:** `__tests__/test_document_upload.py`

## 문제

기존 test_document_upload.py는 업로드 후 리다이렉트 및 목록 노출까지 검증하지만,
업로드 → 문서 상세 페이지 렌더링 → 파싱 트리거 흐름은 미검증.

## 구현

1. 업로드 후 `/documents/{id}` 상세 페이지 렌더링 테스트 추가
2. POST `/documents/{id}/parse` 호출 후 파싱 상태 업데이트 테스트 추가
