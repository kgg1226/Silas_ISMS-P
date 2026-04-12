---
description: "환경 모드, 런타임 모드, 멀티 프로젝트 관련 작업 시 자동 로드"
---
# Governor 실행 모드 상세

## 환경 감지

| 조건 | 모드 | 동작 |
|------|------|------|
| bash 실행 가능 | CLI | sentix CLI 직접 실행, 파일 읽기/쓰기, git |
| 파일 접근만 가능 | 파일 | tasks/tickets/ 직접 생성, CLI를 파일 조작으로 대체 |
| 둘 다 불가 | 대화 | [SENTIX:*] 태그로 상태 추적, 코드 블록으로 제시 |

## 런타임 모드 (.sentix/config.toml)

| 모드 | 실행 주체 | 비용 |
|------|----------|------|
| framework (기본) | Claude Code/Cursor | $0 (구독만) |
| engine | sentix가 API 직접 호출 | API 토큰 과금 |

```bash
sentix run "요청"              # config.toml 기본 모드
sentix run "요청" --engine     # 이번만 engine
sentix run "요청" --single     # 단일 호출 (legacy)
```

## 멀티 프로젝트

| 허용 | 읽기 대상 |
|------|----------|
| 항상 | ../[프로젝트]/INTERFACE.md, README.md |
| 조건부 | ../[프로젝트]/src/** (스키마 연동 시만) |
| 금지 | 다른 프로젝트 파일 수정 |

```bash
sentix context                         # 전체 동기화
sentix context asset-manager --full    # 프로필 자동 생성
sentix context --list                  # 접근 상태 확인
```

## 환경 프로필

```
env-profiles/active.toml → devops 실행 방식
  ssm → AWS SSM / ssh → SSH / manual → 스크립트 / local → Docker
```

## config 파일

```
.sentix/config.toml    — Layer 활성화 + 런타임 모드
.sentix/providers/     — AI 어댑터 (claude, openai, ollama)
.sentix/rules/         — 불변 규칙
```
