# Handoff — 품질 시스템 구축 세션 (완료)

## 완료된 작업

### 브랜치: `claude/investigate-semantic-caching-tSas9`
### PR: kgg1226/sentix#27

6개 레이어 품질 시스템 구축 완료 — 총 16커밋.

### 아키텍처 (6 레이어)

```
L1  파괴 방지      하드 룰 + PreToolUse 훅
L2  결정론적 검증   Quality Gate 5종
L3  입력 강화      Spec Questions + Spec Enricher + constraints.md
L4  자동 학습      Feedback Loop + Lesson Promoter
L5  다중 생성      Multi-Gen (dev × N, 점수 선택) [--multi-gen]
L6  이종 검증      Cross-Review (외부 AI) + 적대적 프롬프트 [--cross-review]
```

### 테스트: 159 pass, 0 fail

### 신규 파일

- `src/lib/quality-gate.js` — 5개 결정론적 검사
- `src/lib/spec-enricher.js` — constraints 로드 + 프롬프트 주입
- `src/lib/spec-questions.js` — 요청 분석 + 구조화 질문
- `src/lib/feedback-loop.js` — Gate 실패 → constraints 자동 추가
- `src/lib/multi-gen.js` — N회 독립 dev + 점수 선택
- `src/lib/cross-review.js` — 이종 모델 API 리뷰
- `.sentix/constraints.md` — 프로젝트 제약 시드
- `__tests__/quality-gate.test.js` (11), `spec-enricher.test.js` (14),
  `spec-questions.test.js` (16), `feedback-loop.test.js` (11),
  `lesson-promoter.test.js` (12), `multi-gen.test.js` (13),
  `cross-review.test.js` (9)

### CLI 사용법

```
sentix run "요청"                                    # 기본 (L1~L4)
sentix run "요청" --multi-gen                        # + L5 다중 생성
sentix run "요청" --cross-review                     # + L6 이종 리뷰
sentix run "요청" --multi-gen --cross-review openai  # L1~L6 전부
```

## 수용된 RISK

- npm audit: package-lock.json 없어 항상 스킵 (zero-dep 의도)
- writeFileSync 원자성: constraints.md 쓰기 중 장애 시 손상 (빈도 매우 낮음)
- diff 15000자 제한: cross-review의 diff 잘림 (대부분 충분)
