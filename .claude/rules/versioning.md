---
paths:
  - "package.json"
  - "INTERFACE.md"
  - "CHANGELOG.md"
  - "src/commands/version.js"
  - "src/lib/semver.js"
  - "src/lib/changelog.js"
---

# Version Management Rules

- 브랜치에서 수동 버전 범프 하지 않는다. CI가 자동으로 처리
- npm 배포된 버전 기준으로 bump (git package.json이 아닌 `npm view` 기준)
- 커밋 메시지로 bump type 자동 감지: feat→minor, fix→patch, feat!→major
- package.json 버전은 CI에서 임시 변경, git에는 커밋 안 함
