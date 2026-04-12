---
description: "sentix self-evolution — 코드 분석 + 이슈 자동 수정"
allowed-tools: ["Bash", "Read", "Edit", "Write", "Glob", "Grep", "Agent"]
---

# Sentix Self-Evolution

$ARGUMENTS

## 실행 순서

1. `npm test` 실행 — 테스트 상태 확인
2. `node bin/sentix.js evolve` 실행 — 정적 분석
3. 이슈가 없으면 "sentix is healthy" 보고 후 종료
4. 이슈가 있으면:
   - critical: 즉시 수정 시도 (CLAUDE.md의 Governor 파이프라인 따름)
   - warning: 수정 시도
   - suggestion: GitHub Issue만 생성

## 수정 시 필수 준수

!`cat docs/agent-methods.md`

## 하드 룰

!`cat .sentix/rules/hard-rules.md`

## 과거 실패 패턴

!`cat tasks/lessons.md`

## 수정 후

- `npm test` 통과 확인
- 변경 사항 git commit
- LESSON_LEARNED가 있으면 tasks/lessons.md에 추가
