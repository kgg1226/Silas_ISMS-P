# Project Constraints — 자동 주입 규칙
#
# 이 파일의 모든 항목은 planner/dev 프롬프트에 자동으로 주입됩니다.
# 시간이 지나면서 lessons.md의 반복 패턴이 여기에 추가됩니다.
#
# 형식: 카테고리별 마크다운 리스트
# 각 항목은 "하지 마라" (금지) 또는 "반드시 하라" (필수) 형태

## Security (보안)

- eval(), exec() 사용 금지 — 코드 인젝션 위험
- f-string으로 SQL 쿼리 조합 금지 — 파라미터 바인딩 사용 (sqlite3 ? placeholder)
- 비밀번호, API 키, 토큰을 코드에 하드코딩 금지 — 환경 변수 사용
- 사용자 입력을 검증 없이 파일 경로, 셸 명령, SQL에 삽입 금지
- Jinja2 템플릿에서 |safe 필터 무분별 사용 금지 — XSS 위험

## Code Quality (코드 품질)

- print() 직접 호출 금지 (스크립트 제외) — logging 모듈 사용
- Any 타입 힌트 사용 금지 — 구체적 타입 명시
- 매직 넘버 금지 — 상수로 추출하여 이름 부여
- 500줄 이상의 파일 생성 금지 — 모듈 분리

## Architecture (아키텍처)

- FastAPI 라우트에서 DB 직접 접근 최소화 — 서비스 레이어 경유
- 동기 I/O를 async 핸들러 안에서 사용 시 주의 — 블로킹 위험
- 순환 import 금지 — 모듈 의존성은 단방향
- 모듈 레벨 DB_PATH 상수 사용 시 환경변수 세팅 순서 주의 (테스트에서 importlib.reload 필요)

## Testing (테스트)

- 새 기능에는 반드시 테스트 추가
- happy path만이 아니라 edge case도 테스트
- 테스트에서 time.sleep() 사용 금지 — 결정론적 검증만
- conftest에서 임시 DB 사용 — 프로덕션 DB 절대 접근 금지

## FastAPI 특화

- TemplateResponse는 starlette 0.38.x 호환 API 사용 (dict-second 방식)
- requirements.txt에 버전 상한 명시 권장 (fastapi<0.115, starlette<0.40)

## Patterns from Lessons (학습된 패턴)

<!-- 아래는 피드백 루프에 의해 자동 추가됩니다 -->
- Starlette 1.0 + FastAPI 0.135 조합에서 TemplateResponse API 호환성 깨짐 → 다운그레이드 필요 (cycle-2)
- database/init_db.py 모듈 레벨 DB_PATH → conftest에서 reload 필수 (cycle-2)
