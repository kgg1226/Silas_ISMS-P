"""
매핑 정확도 테스트 — _compute_relevance_score() 검증

score 기반 자동 매핑(auto_map_document) 신규 로직의 핵심 헬퍼를
단위 테스트로 커버한다.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_item(
    key_checks=None,
    certification_criteria: str = "",
    evidence_examples=None,
) -> dict:
    """테스트용 ISMS-P 항목 dict 생성."""
    import json

    return {
        "key_checks": json.dumps(key_checks) if key_checks is not None else None,
        "certification_criteria": certification_criteria,
        "evidence_examples": json.dumps(evidence_examples) if evidence_examples is not None else None,
    }


# ---------------------------------------------------------------------------
# test_relevance_score_high_match
# ---------------------------------------------------------------------------

def test_relevance_score_high_match():
    """
    섹션 텍스트가 항목의 key_checks·certification_criteria·evidence_examples
    키워드를 폭넓게 포함할 때 score ≥ 0.30을 반환해야 한다.
    """
    from app.services.mapping_service import _compute_relevance_score

    # key_checks(3x 가중치) 항목에 높은 오버랩
    item = _make_item(
        key_checks=["접근통제 정책 수립", "권한 부여 절차", "접근 권한 검토"],
        certification_criteria="정보시스템 접근통제 정책을 수립하고 이행하여야 한다",
        evidence_examples=["접근통제 정책서", "권한 부여 대장"],
    )
    section_text = (
        "접근통제 정책 수립 및 권한 부여 절차에 관한 내용으로 "
        "접근 권한 검토를 통해 정보시스템 접근통제를 관리한다. "
        "접근통제 정책서와 권한 부여 대장을 증적으로 보관한다."
    )

    score = _compute_relevance_score(section_text, item)

    assert isinstance(score, float), "반환 타입은 float이어야 한다"
    assert 0.0 <= score <= 1.0, f"점수는 0~1 범위여야 한다: {score}"
    assert score >= 0.30, f"높은 매칭 시 score ≥ 0.30 기대, 실제: {score}"


# ---------------------------------------------------------------------------
# test_relevance_score_no_match
# ---------------------------------------------------------------------------

def test_relevance_score_no_match():
    """
    섹션 텍스트가 항목 키워드와 전혀 겹치지 않을 때 score < 0.30을
    반환하며 자동 매핑 임계값을 통과하지 못해야 한다.
    """
    from app.services.mapping_service import _compute_relevance_score

    item = _make_item(
        key_checks=["암호화 알고리즘 선정", "키 관리 절차", "암호키 생성"],
        certification_criteria="암호화 키를 안전하게 관리하여야 한다",
        evidence_examples=["암호키 관리 대장", "암호화 정책서"],
    )
    # 완전히 무관한 텍스트 (물리 보안 관련)
    section_text = (
        "건물 출입구 CCTV 설치 현황과 방문객 출입 대장 관리에 관한 내용이다. "
        "물리적 보안 구역 설정 및 출입 통제 절차를 따른다."
    )

    score = _compute_relevance_score(section_text, item)

    assert isinstance(score, float), "반환 타입은 float이어야 한다"
    assert 0.0 <= score <= 1.0, f"점수는 0~1 범위여야 한다: {score}"
    assert score < 0.30, f"무관한 섹션은 score < 0.30 기대, 실제: {score}"


# ---------------------------------------------------------------------------
# test_relevance_score_partial
# ---------------------------------------------------------------------------

def test_relevance_score_partial():
    """
    섹션 텍스트가 항목 키워드 일부만 포함할 때 완전 매칭보다 낮고
    무관한 경우보다는 높은 점수를 반환해야 한다.
    """
    from app.services.mapping_service import _compute_relevance_score

    item = _make_item(
        key_checks=["위험 평가 절차", "위험 수용 기준", "위험 처리 계획", "잔여 위험 승인"],
        certification_criteria="정보보호 위험을 식별하고 평가하여야 한다",
        evidence_examples=["위험 평가 보고서", "위험 처리 계획서", "경영진 승인 문서"],
    )

    # key_checks 4개 중 1개(위험 평가 절차)만 명시적으로 언급
    section_text_partial = (
        "위험 평가 절차에 따라 자산을 분류하고 관리한다. "
        "취약점 점검 결과를 기록하여 보관한다."
    )
    # 전혀 관련 없는 텍스트
    section_text_none = (
        "신규 직원 온보딩 절차와 복무 규정 안내에 관한 내용이다."
    )

    score_partial = _compute_relevance_score(section_text_partial, item)
    score_none = _compute_relevance_score(section_text_none, item)

    assert isinstance(score_partial, float), "반환 타입은 float이어야 한다"
    assert 0.0 <= score_partial <= 1.0, f"부분 매칭 점수 범위 오류: {score_partial}"
    # 부분 매칭 > 완전 미매칭
    assert score_partial > score_none, (
        f"부분 매칭({score_partial:.4f})은 완전 미매칭({score_none:.4f})보다 높아야 한다"
    )


# ---------------------------------------------------------------------------
# 추가 edge-case: 빈 항목 필드
# ---------------------------------------------------------------------------

def test_relevance_score_empty_item_fields():
    """항목 필드가 모두 비어 있으면 0.0을 반환해야 한다."""
    from app.services.mapping_service import _compute_relevance_score

    item = _make_item(key_checks=None, certification_criteria="", evidence_examples=None)
    score = _compute_relevance_score("접근통제 정책 수립 관련 문서", item)

    assert score == 0.0, f"빈 항목 필드 시 0.0 기대, 실제: {score}"


def test_relevance_score_empty_section_text():
    """섹션 텍스트가 비어 있으면 0.0을 반환해야 한다."""
    from app.services.mapping_service import _compute_relevance_score

    item = _make_item(
        key_checks=["접근통제", "권한 관리"],
        certification_criteria="접근통제 정책 수립",
    )
    score = _compute_relevance_score("", item)

    assert score == 0.0, f"빈 섹션 텍스트 시 0.0 기대, 실제: {score}"


def test_relevance_score_range_invariant():
    """임의 입력에 대해 항상 0.0 ≤ score ≤ 1.0 불변식을 만족해야 한다."""
    from app.services.mapping_service import _compute_relevance_score

    cases = [
        ("a" * 500, _make_item(key_checks=["a" * 2], certification_criteria="a" * 2)),
        ("짧음", _make_item(key_checks=["매우 긴 확인사항 텍스트 예시"] * 20)),
        ("보안 정책 수립 절차 및 관리 체계", _make_item(
            key_checks=["보안 정책", "수립 절차"],
            certification_criteria="관리 체계 수립",
            evidence_examples=["보안 정책서"],
        )),
    ]
    for sec_text, item in cases:
        score = _compute_relevance_score(sec_text, item)
        assert 0.0 <= score <= 1.0, f"범위 오류: score={score}, text={sec_text[:30]!r}"
