#!/bin/sh
# Sentix UserPromptSubmit hook
#
# 매 사용자 프롬프트 제출 시 실행되어 짧은 Governor 리마인더를
# 컨텍스트에 주입한다. SessionStart 는 1회성이라 세션이 길어질수록
# 망각될 수 있으므로 이 훅이 매 턴 "당신은 Governor다" 를 상기시킨다.
#
# 주의: 출력이 너무 길면 사용자 경험이 나빠진다 — 짧게 유지.
#
# 등록: .claude/settings.json hooks.UserPromptSubmit

# 파이프라인 내부 에이전트는 간소한 리마인더만
if [ "$SENTIX_PIPELINE" = "true" ]; then
  cat <<'AGENT_EOF'
[SENTIX AGENT] Write/Edit로 실제 파일을 수정하세요. 텍스트 출력만 하지 마세요.
AGENT_EOF
  exit 0
fi

cat <<'EOF'
[SENTIX REMINDER]
- 코드 변경 요청 = 반드시 `sentix run "<요청>"` 으로 실행 (직접 코딩 금지)
- sentix run이 L1~L6 전체 품질 파이프라인을 자동 실행합니다
- 직접 Write/Edit 금지 (PreToolUse 훅이 차단)
- 하드 룰 6개: 테스트 스냅샷 / SCOPE 준수 / export 보존 / 테스트 보존 / 순삭제 50줄 / 핸들러 보존
- 질문/탐색은 예외 (읽기 도구는 허용)
- 코드 변경이 필요하면: sentix run "<요청>" 또는 sentix ticket create "<설명>"
EOF

exit 0
