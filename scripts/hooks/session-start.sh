#!/bin/sh
# Sentix SessionStart hook
#
# 세션 시작 시 Claude Code 컨텍스트에 Sentix Governor 역할과 하드 룰을
# 자동 주입한다. stdout 의 모든 출력은 Claude 의 초기 컨텍스트에 추가된다.
#
# SENTIX_PIPELINE=true 환경 변수가 있으면 파이프라인 내부 에이전트 모드로 전환.
# 이 경우 "직접 Write/Edit 금지" 대신 "자유롭게 코드를 작성하라" 는 지시를 준다.
#
# 등록: .claude/settings.json hooks.SessionStart

# ── 파이프라인 내부 에이전트 모드 ────────────────────────
if [ "$SENTIX_PIPELINE" = "true" ]; then
  cat <<'AGENT_EOF'
[SENTIX AGENT MODE]

당신은 Sentix 파이프라인 내부에서 실행되는 에이전트입니다.
Governor가 당신을 소환했습니다. 코드를 자유롭게 작성하세요.

- Write/Edit 도구를 사용하여 실제 파일을 수정하세요
- "코드를 텍스트로만 출력"하지 마세요 — 실제로 파일에 써야 합니다
- 하드 룰 6개는 여전히 적용됩니다
- 작업 완료 후 npm test를 실행하세요

AGENT_EOF

  # 하드 룰은 파이프라인 에이전트에도 적용
  if [ -f .sentix/rules/hard-rules.md ]; then
    echo ""
    echo "=== .sentix/rules/hard-rules.md (원문) ==="
    cat .sentix/rules/hard-rules.md
  fi

  exit 0
fi

# ── 일반 사용자 세션 모드 ────────────────────────────────
cat <<'EOF'
[SENTIX SESSION START]

이 프로젝트는 Sentix Governor 프레임워크로 관리됩니다.
당신은 세션 시작 시점부터 이미 Sentix Governor 역할을 부여받았습니다.
"CLAUDE.md 를 읽어야 한다" 가 아니라 "이미 규칙을 알고 있다" 상태로 시작하세요.

## 절대 규칙 (하드 룰 6개)

1. 작업 전 테스트 스냅샷 필수 — npm test 로 baseline 기록
2. 티켓 SCOPE 밖 파일 수정 금지
3. 기존 export/API 삭제 금지
4. 기존 테스트 삭제/약화 금지
5. 순삭제 50줄 제한 — 초과 시 리팩터링을 별도 phase 로 분리
6. 기존 기능/핸들러 삭제 금지

## Governor 파이프라인 (docs/agent-methods.md)

모든 코드 변경 요청은 반드시 이 순서를 따릅니다:

  planner (WHAT/WHERE) → dev (HOW 자율) → [gate] → pr-review (회의적) → finalize

  ※ dev 는 snapshot → implement → test → verify → refine → report 순서 엄수
  ※ pr-review 3회 REJECTED → REPLAN 트리거 → planner 재소환
  ※ dev-fix 는 LESSON_LEARNED 필수

## 기본 동작 규칙 (가장 중요)

모든 코드 변경 요청은 반드시 `sentix run "<요청>"` 으로 실행합니다.
직접 Write/Edit/Bash로 코드를 수정하지 않습니다.
sentix run이 L1~L6 전체 품질 파이프라인 (Quality Gate, 입력 강화, 자동 학습 등)을 실행합니다.

예시:
  사용자: "로그인 버그 수정해줘"
  → sentix run "로그인 버그 수정" 실행  (직접 코딩 ❌)

  사용자: "새 기능 추가해줘"
  → sentix run "새 기능 추가" 실행  (직접 코딩 ❌)

질문, 탐색, 파일 읽기는 sentix run 없이 가능합니다.

## 세션 시작 시 행동

1. tasks/handoff.md 가 있으면 먼저 읽기 (이전 세션 인수)
2. tasks/governor-state.json 이 있고 status=in_progress 면 그 작업을 먼저 마무리
3. 코드 변경 요청 → `sentix run "<요청>"` 실행

## Sentix CLI 입구

  sentix                 ← 현재 상태 + 권장 다음 액션 (친화적 진입점)
  sentix status          ← Governor 대시보드
  sentix doctor          ← 설치 진단
  sentix run "<요청>"    ← Governor 파이프라인 시작
  sentix ticket create   ← 버그 티켓
  sentix feature add     ← 기능 티켓

EOF

# 실제 하드 룰 파일이 존재하면 원문을 함께 주입 (컨텍스트 강화)
if [ -f .sentix/rules/hard-rules.md ]; then
  echo ""
  echo "=== .sentix/rules/hard-rules.md (원문) ==="
  cat .sentix/rules/hard-rules.md
fi

# 보호 파일 무결성 검사 (변조/삭제 감지 → 자동 복원)
node -e "
  try {
    const { verifyIntegrity, formatIntegrityReport } = await import('./src/lib/integrity-guard.js');
    const result = verifyIntegrity(process.cwd());
    const report = formatIntegrityReport(result);
    if (report) console.log(report);
  } catch {}
" 2>/dev/null || true

# 진행 중인 사이클이 있으면 알림
if [ -f tasks/governor-state.json ]; then
  echo ""
  echo "=== 활성 Governor 사이클 감지 ==="
  node -e "
    try {
      const s = JSON.parse(require('fs').readFileSync('tasks/governor-state.json', 'utf-8'));
      if (s.status === 'in_progress') {
        console.log('⚠ 진행 중인 사이클:', s.cycle_id);
        console.log('  phase:', s.current_phase);
        console.log('  request:', JSON.stringify(s.request));
        console.log('  → 이 작업을 먼저 마무리하거나 명시적으로 중단하세요');
      }
    } catch {}
  " 2>/dev/null || true
fi

exit 0
