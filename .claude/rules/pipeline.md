---
paths:
  - "src/lib/pipeline.js"
  - "src/commands/run.js"
  - ".claude/agents/**"
---

# Pipeline Rules

- 각 phase는 `--output-format json`으로 호출하여 결과 파싱
- `.claude/agents/` 에 에이전트가 있으면 `--agent` 플래그 자동 사용
- planner는 WHAT/WHERE만 정의. HOW(구현 방법) 명세 금지
- dev의 verify()는 하드룰만. 품질 판단은 pr-review에 위임
- pr-review는 회의적 판정. 의심스러우면 REJECTED
- dev-fix는 LESSON_LEARNED 필수
