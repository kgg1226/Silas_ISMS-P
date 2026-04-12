---
paths:
  - ".github/workflows/**"
---

# CI/CD Workflow Rules

- YAML 문법 검증 후 push (sed 멀티라인, 특수문자 주의)
- GitHub Actions에서 `GITHUB_TOKEN`으로 main push 불가 (403). git commit/push 넣지 않는다
- `--provenance` 플래그는 Node 24+에서만 사용 (Node 22 이하에서 OIDC 버그 npm/cli#8976)
- npm publish는 `NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}`으로 인증
- 한 번에 여러 개 바꾸지 않는다. 하나 고치고 확인하고 다음
- workflow 변경은 가장 단순한 방식부터 동작 확인 후 확장
