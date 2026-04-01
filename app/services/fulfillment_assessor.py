"""
충족 수준 자동 평가 엔진 (Fulfillment Assessor)

각 ISMS-P 항목의 key_checks(주요 확인사항)를 개별 체크포인트로 분해하고,
문서 섹션 내용이 각 포인트를 실제로 다루는지 검사하여 충족 등급을 산정한다.

기존 키워드 겹침 방식 → 체크포인트 기반 정밀 평가로 대체.

등급 산정 기준:
    full      : 체크포인트 70% 이상 충족 + 부정 지표 없음
    partial   : 체크포인트 30% 이상 충족
    reference : 체크포인트 30% 미만 (언급은 있으나 실질 충족 부족)
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------

@dataclass
class CheckpointResult:
    """개별 체크포인트 평가 결과."""
    checkpoint: str          # 원본 확인사항 텍스트
    key_terms: list[str]     # 핵심 용어
    matched_terms: list[str] # 문서에서 발견된 용어
    score: float             # 0.0 ~ 1.0
    addressed: bool          # 충족 여부


@dataclass
class AssessmentResult:
    """종합 평가 결과."""
    coverage_level: str            # full / partial / reference
    confidence_score: float        # 0.0 ~ 1.0
    total_checkpoints: int
    addressed_count: int
    checkpoint_results: list[CheckpointResult] = field(default_factory=list)
    negative_indicators: list[str] = field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "coverage_level": self.coverage_level,
            "confidence_score": round(self.confidence_score, 3),
            "total_checkpoints": self.total_checkpoints,
            "addressed_count": self.addressed_count,
            "addressed_ratio": round(self.addressed_count / max(self.total_checkpoints, 1), 2),
            "negative_indicators": self.negative_indicators,
            "reasoning": self.reasoning,
            "checkpoints": [
                {
                    "checkpoint": cr.checkpoint[:80],
                    "score": round(cr.score, 2),
                    "addressed": cr.addressed,
                    "matched": cr.matched_terms,
                }
                for cr in self.checkpoint_results
            ],
        }

    def summary_text(self) -> str:
        """매핑 notes에 저장할 요약 텍스트."""
        ratio = self.addressed_count / max(self.total_checkpoints, 1)
        lines = [
            f"[자동평가] {self.coverage_level} ({ratio:.0%}, {self.addressed_count}/{self.total_checkpoints} 체크포인트)",
        ]
        if self.negative_indicators:
            lines.append(f"  부정지표: {', '.join(self.negative_indicators)}")
        for cr in self.checkpoint_results:
            mark = "✓" if cr.addressed else "✗"
            lines.append(f"  {mark} {cr.checkpoint[:60]}{'...' if len(cr.checkpoint) > 60 else ''}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 부정 지표 (문서가 해당 사항을 아직 충족하지 않음을 나타내는 표현)
# ---------------------------------------------------------------------------

NEGATIVE_INDICATORS = [
    "미수립", "미비", "미흡", "미이행", "미실시", "미적용", "미반영",
    "예정", "계획중", "계획 중", "향후", "추후",
    "검토중", "검토 중", "수립중", "수립 중",
    "미확인", "부재", "없음", "누락",
    "위반", "미준수", "위배",
]

# 핵심 개념어 — 체크포인트에서 추출 시 불용어 제거에 사용
STOPWORDS = {
    "있는가", "하고", "하는가", "하여야", "한다", "위한", "대한",
    "이를", "그에", "따른", "것을", "수립", "이행", "운영",
    "관한", "통하여", "필요한", "적절한", "정기적", "주기적",
    "확인", "점검", "관리", "방안", "절차", "대책", "조치",
    "해야", "되어야", "포함", "반영", "고려", "기반",
    "여부", "등의", "또한", "되는", "되고", "하며",
}

# 문서 유형 ↔ 항목 증적유형 매칭 가중치
DOC_TYPE_BOOST = {
    ("정책서", "정책"): 0.1,
    ("지침서", "지침"): 0.1,
    ("절차서", "절차"): 0.1,
    ("계획서", "계획"): 0.1,
    ("보고서", "보고"): 0.08,
    ("회의록", "회의"): 0.05,
    ("교육자료", "교육"): 0.08,
}


# ---------------------------------------------------------------------------
# 핵심 로직
# ---------------------------------------------------------------------------

def _parse_json_list(raw: Optional[str]) -> list[str]:
    """JSON 배열 문자열 파싱."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return [raw.strip()] if raw and raw.strip() else []


def _extract_key_terms(text: str) -> list[str]:
    """
    체크포인트 텍스트에서 핵심 용어를 추출한다.

    전략:
    1. 한국어 복합명사/전문용어 우선 추출 (3글자 이상)
    2. 영문 약어/기술용어 추출
    3. 불용어 제거
    """
    terms = []

    # 전문 용어 패턴 (복합명사) — 3글자 이상 한국어
    korean_words = re.findall(r"[가-힣]{3,}", text)
    for w in korean_words:
        if w not in STOPWORDS and len(w) >= 3:
            terms.append(w)

    # 2글자 한국어도 전문용어면 포함
    two_char = re.findall(r"[가-힣]{2}", text)
    important_two = {
        "정책", "지침", "계획", "교육", "감사", "로그", "백업", "암호",
        "인증", "통제", "권한", "계정", "자산", "위험", "보호", "대응",
        "복구", "탐지", "차단", "변경", "승인", "분류", "폐기", "동의",
        "고지", "처리", "위탁", "파기", "열람", "정정", "삭제", "약관",
        "침해", "사고", "훈련", "점검", "진단", "평가", "분석", "검토",
        "기록", "보관", "전송", "접속", "네트워크", "서버",
    }
    for w in two_char:
        if w in important_two:
            terms.append(w)

    # 영문 기술 용어
    eng_terms = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", text)
    for t in eng_terms:
        if len(t) >= 2:
            terms.append(t.upper())

    return list(dict.fromkeys(terms))  # 순서 유지 중복 제거


def _check_addressed(key_terms: list[str], content: str, content_lower: str) -> tuple[float, list[str]]:
    """
    문서 섹션 내용이 체크포인트의 핵심 용어를 얼마나 포함하는지 평가.

    Returns:
        (score 0.0~1.0, matched_terms)
    """
    if not key_terms:
        return 0.0, []

    matched = []
    for term in key_terms:
        # 한글은 그대로 검색, 영문은 대소문자 무시
        if re.search(r"[가-힣]", term):
            if term in content:
                matched.append(term)
        else:
            if term.lower() in content_lower:
                matched.append(term)

    # 매칭 비율
    raw_ratio = len(matched) / len(key_terms)

    # 핵심 용어 가중: 앞쪽 용어(보통 더 중요)에 가중치
    if matched and len(key_terms) >= 3:
        # 앞쪽 50% 용어 매칭 보너스
        front_terms = key_terms[: max(len(key_terms) // 2, 1)]
        front_matched = sum(1 for t in front_terms if t in matched)
        front_ratio = front_matched / len(front_terms)
        score = raw_ratio * 0.6 + front_ratio * 0.4
    else:
        score = raw_ratio

    return min(score, 1.0), matched


def _detect_negatives(content: str) -> list[str]:
    """문서 내용에서 부정 지표를 탐지."""
    found = []
    for indicator in NEGATIVE_INDICATORS:
        if indicator in content:
            found.append(indicator)
    return found


def assess_fulfillment(
    section_content: str,
    item_code: str,
    doc_type: str = "",
    conn: Optional[sqlite3.Connection] = None,
) -> AssessmentResult:
    """
    문서 섹션 내용을 분석하여 특정 항목의 충족 수준을 자동 평가한다.

    Args:
        section_content: 문서 섹션의 전체 텍스트
        item_code: ISMS-P 항목 코드
        doc_type: 문서 유형 (선택)
        conn: DB 연결 (선택, 없으면 자동 생성)

    Returns:
        AssessmentResult
    """
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        close_conn = True

    try:
        # 항목 정보 로드
        row = conn.execute(
            """SELECT item_code, item_title, certification_criteria,
                      key_checks, evidence_examples
               FROM isms_requirements WHERE item_code = ?""",
            (item_code,),
        ).fetchone()

        if not row:
            return AssessmentResult(
                coverage_level="reference",
                confidence_score=0.0,
                total_checkpoints=0,
                addressed_count=0,
                reasoning=f"항목 {item_code}를 찾을 수 없음",
            )

        # 주요 확인사항 → 체크포인트 분해
        key_checks = _parse_json_list(row["key_checks"])

        if not key_checks:
            # key_checks가 없으면 인증기준 자체를 단일 체크포인트로 사용
            criteria = row["certification_criteria"] or ""
            if criteria:
                key_checks = [criteria]
            else:
                return AssessmentResult(
                    coverage_level="reference",
                    confidence_score=0.0,
                    total_checkpoints=0,
                    addressed_count=0,
                    reasoning="주요 확인사항 및 인증기준 데이터 없음",
                )

        content = section_content or ""
        content_lower = content.lower()

        # 각 체크포인트 평가
        checkpoint_results: list[CheckpointResult] = []
        for check_text in key_checks:
            terms = _extract_key_terms(check_text)
            score, matched = _check_addressed(terms, content, content_lower)

            checkpoint_results.append(CheckpointResult(
                checkpoint=check_text,
                key_terms=terms,
                matched_terms=matched,
                score=score,
                addressed=score >= 0.35,  # 35% 이상 용어 매칭 시 "다룸"으로 판정
            ))

        # 부정 지표 탐지
        negatives = _detect_negatives(content)

        # 종합 점수 산정
        total = len(checkpoint_results)
        addressed = sum(1 for cr in checkpoint_results if cr.addressed)
        ratio = addressed / max(total, 1)

        # 기본 신뢰도 = 체크포인트 스코어의 가중 평균
        if checkpoint_results:
            avg_score = sum(cr.score for cr in checkpoint_results) / total
        else:
            avg_score = 0.0

        # 문서 유형 보너스
        type_bonus = 0.0
        if doc_type:
            evidence_text = " ".join(_parse_json_list(row["evidence_examples"]))
            for (dtype, keyword), bonus in DOC_TYPE_BOOST.items():
                if dtype in doc_type and keyword in evidence_text:
                    type_bonus = bonus
                    break

        confidence = min(avg_score + type_bonus, 1.0)

        # 부정 지표 감점
        neg_penalty = len(negatives) * 0.05
        confidence = max(confidence - neg_penalty, 0.0)

        # 등급 결정
        if ratio >= 0.70 and not negatives:
            coverage_level = "full"
        elif ratio >= 0.70 and negatives:
            coverage_level = "partial"  # 체크포인트는 충족했지만 부정 지표 있음
        elif ratio >= 0.30:
            coverage_level = "partial"
        else:
            coverage_level = "reference"

        # 추론 로그
        reasoning_parts = [
            f"체크포인트 {addressed}/{total} 충족 ({ratio:.0%})",
        ]
        if negatives:
            reasoning_parts.append(f"부정지표 {len(negatives)}건: {', '.join(negatives[:3])}")
        if type_bonus > 0:
            reasoning_parts.append(f"문서유형 보너스 +{type_bonus:.2f}")
        reasoning = " | ".join(reasoning_parts)

        return AssessmentResult(
            coverage_level=coverage_level,
            confidence_score=confidence,
            total_checkpoints=total,
            addressed_count=addressed,
            checkpoint_results=checkpoint_results,
            negative_indicators=negatives,
            reasoning=reasoning,
        )

    finally:
        if close_conn:
            conn.close()


def assess_mapping(
    mapping_id: int,
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[AssessmentResult]:
    """
    기존 매핑의 충족 수준을 재평가한다.

    매핑 ID로 문서 섹션 내용과 항목을 조회 → assess_fulfillment 호출.
    """
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        close_conn = True

    try:
        mapping = conn.execute(
            """SELECT m.item_code, m.section_id, m.document_id,
                      d.doc_type, s.content AS section_content,
                      s.section_title AS sec_title
               FROM document_item_mappings m
               JOIN documents d ON m.document_id = d.id
               LEFT JOIN document_sections s ON m.section_id = s.id
               WHERE m.id = ?""",
            (mapping_id,),
        ).fetchone()

        if not mapping:
            return None

        content = mapping["section_content"] or ""
        if mapping["sec_title"]:
            content = mapping["sec_title"] + " " + content

        result = assess_fulfillment(
            section_content=content,
            item_code=mapping["item_code"],
            doc_type=mapping["doc_type"] or "",
            conn=conn,
        )

        # 매핑 업데이트
        conn.execute(
            """UPDATE document_item_mappings
               SET coverage_level = ?, confidence_score = ?, notes = ?
               WHERE id = ?""",
            (result.coverage_level, result.confidence_score, result.summary_text(), mapping_id),
        )
        conn.commit()

        return result

    finally:
        if close_conn:
            conn.close()


def batch_assess_document(document_id: int) -> dict:
    """
    문서의 모든 매핑을 일괄 재평가한다.

    Returns:
        {"assessed": int, "results": {"full": int, "partial": int, "reference": int}}
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    try:
        mappings = conn.execute(
            "SELECT id FROM document_item_mappings WHERE document_id = ?",
            (document_id,),
        ).fetchall()

        results = {"full": 0, "partial": 0, "reference": 0}
        assessed = 0

        for m in mappings:
            result = assess_mapping(m["id"], conn=conn)
            if result:
                results[result.coverage_level] = results.get(result.coverage_level, 0) + 1
                assessed += 1

        return {"assessed": assessed, "results": results}

    finally:
        conn.close()
