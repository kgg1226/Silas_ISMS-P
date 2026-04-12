# TICKET-008: 의존성 버전 상한 명시 (starlette)

- **Status:** in_progress
- **Priority:** P2
- **Scope:** `requirements.txt`

## 문제

cycle-2 lessons에서 starlette 1.0 + FastAPI 0.135 조합에서 호환성 문제 발생.
fastapi<0.115 상한은 이미 추가됐으나, starlette는 명시적 상한이 없어
간접 의존성으로 0.40+ 버전이 설치될 수 있음.

## 구현

`requirements.txt`에 `starlette>=0.37.0,<0.40` 추가.
