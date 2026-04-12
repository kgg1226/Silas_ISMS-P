# TICKET-012: 다국어/번역 준비

- **Status:** done
- **Priority:** P3
- **Scope:** `app/templates/**`, `app/i18n.py`, `app/template_helpers.py`

## 문제

해외 파트너(영어/일본어 사용자) 대응을 위한 i18n 기반 부재.

## 구현

1. `app/i18n.py` — 번역 레지스트리
   - `get_text(key, locale)` 공개 API
   - 한국어(ko) 완전 구현, 영어(en)/일본어(ja) 스텁
   - 누락 키는 ko 폴백 → 최종 폴백은 키 자체 (절대 빈 문자열 반환 안 함)
2. `app/template_helpers.py` — Jinja2 글로벌 `t()` 등록 헬퍼
3. `app/templates/base.html` — 네비게이션에 `t()` 적용
4. 모든 라우터에 `setup_i18n(templates)` 호출 추가
5. `__tests__/test_i18n.py` 단위 테스트 추가 (22케이스)
