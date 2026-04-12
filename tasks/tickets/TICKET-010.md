# TICKET-010: 매핑 자동화 정밀도 개선

- **Status:** done
- **Priority:** P3
- **Scope:** `app/services/mapping_service.py`, `app/services/fulfillment_assessor.py`

## 문제

기존 단순 토큰 오버랩 방식 → 가중치 기반 recall 계산으로 업그레이드 필요.
섹션 길이 편향(긴 섹션이 무조건 높은 점수)을 보정하는 로직이 없었음.

## 구현

1. `_compute_relevance_score(section_text, item)` 신규 추가
   - key_checks(3x) / certification_criteria(2x) / evidence_examples(1x) 가중치
   - 섹션 토큰 수 기반 length_factor 길이 편향 보정
   - 임계값 0.30 (이전 0.15에서 상향) — 노이즈 매핑 감소
2. `auto_map_document` Phase 1 로직을 `_compute_relevance_score` 기반으로 교체
3. `__tests__/test_mapping_accuracy.py` 단위 테스트 추가 (6케이스)
