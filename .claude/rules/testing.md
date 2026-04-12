---
paths:
  - "**/*.test.*"
  - "**/*.spec.*"
  - "__tests__/**"
---

# Testing Rules

- 기존 테스트의 describe/it/test 블록을 삭제하지 않는다
- 테스트가 실패하면 코드를 고친다, 테스트를 고치지 않는다
- 새 기능에는 반드시 테스트를 추가한다
- happy path만이 아니라 edge case도 테스트한다
- 테스트 실행: `npm test`
