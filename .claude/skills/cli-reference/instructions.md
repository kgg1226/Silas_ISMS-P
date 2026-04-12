---
description: "sentix CLI 명령어 사용 시 자동 로드"
---
# Sentix CLI 전체 명령어 참조

## 핵심 명령어

| 명령 | 설명 |
|------|------|
| `sentix run "요청"` | Governor 파이프라인 실행 |
| `sentix run "요청" --resume` | 중단된 파이프라인 재개 |
| `sentix status` | Governor 상태 + Memory Layer 요약 |
| `sentix doctor` | 설치 상태 진단 |
| `sentix update` | 프레임워크 파일 동기화 (worktree도 포함) |
| `sentix evolve` | 자기 분석 (정적, AI 없음) |

## 티켓

| 명령 | 설명 |
|------|------|
| `sentix ticket create "설명"` | 버그 티켓 생성 |
| `sentix ticket create "설명" --severity critical` | severity 지정 |
| `sentix ticket list` | 전체 목록 |
| `sentix ticket list --status open` | 필터링 |
| `sentix feature add "설명"` | 기능 티켓 + impact 분석 |

## 버전

| 명령 | 설명 |
|------|------|
| `sentix version current` | 현재 버전 |
| `sentix version bump` | auto 감지 (feat→minor, fix→patch) |
| `sentix version bump patch/minor/major` | 수동 |
| `sentix version changelog` | CHANGELOG 미리보기 |

## 안전어

| 명령 | 설명 |
|------|------|
| `sentix safety set <word>` | 최초 설정 |
| `sentix safety reset <old> <new>` | 변경 |
| `sentix safety verify <word>` | 검증 |
| `sentix safety unlock <key>` | 잠금 해제 |
| `sentix safety status` | 상태 |

## 컨텍스트

| 명령 | 설명 |
|------|------|
| `sentix context` | 전체 프로젝트 동기화 |
| `sentix context <name> --full` | 특정 프로젝트 + 프로필 생성 |
| `sentix context --list` | 프로젝트 접근 상태 |
| `sentix metrics` | 에이전트 성공률 분석 |
