"""
매핑 CRUD + 자동 매핑 엔진

수동 매핑: 사용자가 문서 섹션 → 통제항목 매핑 생성
자동 매핑: 키워드 매칭으로 매핑 후보 제안 (verified=0)
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _parse_json(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return [raw] if raw and raw.strip() else []


def _log_mapping(conn, action, mapping_id=None, document_id=None, item_code=None, detail=""):
    conn.execute(
        "INSERT INTO mapping_logs (action, mapping_id, document_id, item_code, detail) VALUES (?,?,?,?,?)",
        (action, mapping_id, document_id, item_code, detail),
    )


# ---------------------------------------------------------------------------
# 수동 매핑 CRUD
# ---------------------------------------------------------------------------

def create_mapping(
    document_id: int,
    item_code: str,
    section_id: Optional[int] = None,
    coverage_level: str = "partial",
    notes: str = "",
    created_by: str = "manual",
) -> dict:
    """수동 매핑 생성."""
    conn = _get_conn()

    # 중복 확인
    existing = conn.execute(
        """SELECT id FROM document_item_mappings
           WHERE document_id = ? AND COALESCE(section_id, 0) = ? AND item_code = ?""",
        (document_id, section_id or 0, item_code),
    ).fetchone()

    if existing:
        conn.close()
        return {"success": False, "error": "동일 매핑이 이미 존재합니다.", "mapping_id": existing["id"]}

    cursor = conn.execute(
        """INSERT INTO document_item_mappings
           (document_id, section_id, item_code, fulfillment_type,
            coverage_level, confidence_score, mapping_source, verified,
            notes, created_by)
           VALUES (?, ?, ?, 'document', ?, 1.0, 'manual', 1, ?, ?)""",
        (document_id, section_id, item_code, coverage_level, notes, created_by),
    )
    mapping_id = cursor.lastrowid
    _log_mapping(conn, "create", mapping_id, document_id, item_code, f"수동 매핑 생성 ({coverage_level})")
    conn.commit()
    conn.close()
    return {"success": True, "mapping_id": mapping_id, "error": None}


def verify_mapping(mapping_id: int, verified_by: str = "admin") -> bool:
    """매핑 검증 승인."""
    conn = _get_conn()
    conn.execute(
        """UPDATE document_item_mappings
           SET verified = 1, verified_by = ?, verified_at = datetime('now')
           WHERE id = ?""",
        (verified_by, mapping_id),
    )
    _log_mapping(conn, "verify", mapping_id, detail=f"검증자: {verified_by}")
    conn.commit()
    conn.close()
    return True


def reject_mapping(mapping_id: int) -> bool:
    """매핑 거부 (삭제)."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT document_id, item_code FROM document_item_mappings WHERE id = ?",
        (mapping_id,),
    ).fetchone()
    if row:
        _log_mapping(conn, "reject", mapping_id, row["document_id"], row["item_code"])
        conn.execute("DELETE FROM document_item_mappings WHERE id = ?", (mapping_id,))
        conn.commit()
    conn.close()
    return True


def get_all_mappings(
    verified_only: bool = False,
    item_code: str = "",
    document_id: int = 0,
) -> list[dict]:
    """전체 매핑 목록 조회."""
    conn = _get_conn()
    query = """
        SELECT m.*, d.title as doc_title, d.doc_type, d.version as doc_version,
               r.item_title, r.section_title as item_section_title,
               s.section_number, s.section_title as sec_title
        FROM document_item_mappings m
        JOIN documents d ON m.document_id = d.id
        JOIN isms_requirements r ON m.item_code = r.item_code
        LEFT JOIN document_sections s ON m.section_id = s.id
        WHERE 1=1
    """
    params = []
    if verified_only:
        query += " AND m.verified = 1"
    if item_code:
        query += " AND m.item_code = ?"
        params.append(item_code)
    if document_id:
        query += " AND m.document_id = ?"
        params.append(document_id)
    query += " ORDER BY m.item_code, m.document_id"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_item_mappings(item_code: str) -> list[dict]:
    """특정 항목에 매핑된 문서 목록 (심사관 뷰용)."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT m.*, d.title as doc_title, d.doc_type, d.version as doc_version,
                  d.status as doc_status, d.expiry_date,
                  s.section_number, s.section_title as sec_title,
                  s.page_start, s.page_end
           FROM document_item_mappings m
           JOIN documents d ON m.document_id = d.id
           LEFT JOIN document_sections s ON m.section_id = s.id
           WHERE m.item_code = ?
           ORDER BY m.verified DESC, m.confidence_score DESC""",
        (item_code,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_items_for_mapping() -> list[dict]:
    """매핑용 항목 목록 (코드 + 제목)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT item_code, item_title FROM isms_requirements ORDER BY item_code"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# 자동 매핑 엔진 (키워드 기반)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """간단한 한국어 토큰화: 2글자 이상 단어 추출."""
    # 특수문자 제거, 공백 분리
    words = re.findall(r"[가-힣a-zA-Z0-9]{2,}", text)
    return set(w for w in words if len(w) >= 2)


def _compute_relevance_score(section_text: str, item: dict) -> float:
    """
    섹션 텍스트와 ISMS-P 항목 간의 관련도 점수를 계산한다.

    가중치 체계:
        key_checks             → 3x  (주요 확인사항, 가장 직접적인 매핑 근거)
        certification_criteria → 2x  (인증기준)
        evidence_examples      → 1x  (증적 예시)

    텍스트 길이 편향 보정:
        섹션 토큰 수로 정규화하여 긴 섹션이 무조건 높은 점수를
        받는 bias를 제거한다.  섹션 토큰이 20개 미만이면 최대 20% 감점.

    Args:
        section_text: 섹션 제목 + 본문을 합친 문자열
        item: key_checks, certification_criteria, evidence_examples
              필드를 갖는 dict (원본 텍스트 또는 None)

    Returns:
        0.0 ~ 1.0 사이의 신뢰도 점수
    """
    sec_tokens = _tokenize(section_text)
    sec_len = max(len(sec_tokens), 1)

    kc_text = " ".join(_parse_json(item.get("key_checks") or ""))
    ee_text = " ".join(_parse_json(item.get("evidence_examples") or ""))
    crit_text = item.get("certification_criteria") or ""

    kc_tokens = _tokenize(kc_text)
    crit_tokens = _tokenize(crit_text)
    ee_tokens = _tokenize(ee_text)

    weighted_hits = 0.0
    total_weight = 0.0

    for token_set, weight in [
        (kc_tokens, 3.0),
        (crit_tokens, 2.0),
        (ee_tokens, 1.0),
    ]:
        if token_set:
            overlap = len(sec_tokens & token_set)
            # 겹친 토큰 수를 항목 토큰 집합 크기로 나눠 recall 계산
            recall = overlap / max(len(token_set), 1)
            weighted_hits += recall * weight
            total_weight += weight

    if total_weight == 0.0:
        return 0.0

    # 가중 recall (0~1 범위)
    raw_score = weighted_hits / total_weight

    # 텍스트 길이 편향 보정: 섹션 토큰 20개 미만이면 최대 20% 감점
    length_factor = min(sec_len / 20.0, 1.0)

    score = raw_score * (0.8 + 0.2 * length_factor)
    return round(min(score, 1.0), 6)


def auto_map_document(document_id: int) -> dict:
    """
    문서의 파싱된 섹션을 키워드 매칭으로 항목에 자동 매핑.
    매핑 후보를 찾으면 fulfillment_assessor로 체크포인트 기반 충족 수준을 산정한다.

    Phase 1: _compute_relevance_score()로 후보 필터링 (score ≥ 0.30)
             key_checks=3x, certification_criteria=2x, evidence_examples=1x 가중치 적용,
             텍스트 길이 편향 보정 포함.
    Phase 2: fulfillment_assessor로 체크포인트 기반 충족 수준 정밀 평가

    Returns:
        {"suggestions": int, "skipped": int, "assessment": {"full": int, "partial": int, "reference": int}}
    """
    from app.services.fulfillment_assessor import assess_fulfillment

    conn = _get_conn()

    # 문서 유형 조회
    doc_row = conn.execute("SELECT doc_type FROM documents WHERE id = ?", (document_id,)).fetchone()
    doc_type = doc_row["doc_type"] if doc_row else ""

    # 섹션 로드
    sections = conn.execute(
        "SELECT id, section_number, section_title, content FROM document_sections WHERE document_id = ?",
        (document_id,),
    ).fetchall()

    if not sections:
        conn.close()
        return {"suggestions": 0, "skipped": 0, "assessment": {}, "error": "파싱된 섹션이 없습니다."}

    # 항목 로드
    items = conn.execute(
        """SELECT item_code, item_title, certification_criteria,
                  key_checks, evidence_examples
           FROM isms_requirements ORDER BY item_code"""
    ).fetchall()

    # 항목별 캐시 — 원본 텍스트 필드 보존 (_compute_relevance_score가 사용)
    item_tokens: list[dict] = []
    for item in items:
        item_tokens.append({
            "item_code": item["item_code"],
            # _compute_relevance_score()가 기대하는 원본 텍스트 필드
            "key_checks": item["key_checks"],
            "certification_criteria": item["certification_criteria"],
            "evidence_examples": item["evidence_examples"],
        })

    suggestions = 0
    skipped = 0
    assessment_counts = {"full": 0, "partial": 0, "reference": 0}

    for sec in sections:
        sec_text = f"{sec['section_title'] or ''} {sec['content'] or ''}"

        if len(_tokenize(sec_text)) < 3:
            continue  # 너무 짧은 섹션 스킵

        for it in item_tokens:
            # Phase 1: 점수 기반 후보 필터링 (_compute_relevance_score 사용)
            relevance = _compute_relevance_score(sec_text, it)

            # 임계값: 0.30 미만은 노이즈 매핑으로 간주하여 제외
            if relevance >= 0.30:
                # 중복 체크
                existing = conn.execute(
                    """SELECT id FROM document_item_mappings
                       WHERE document_id = ? AND COALESCE(section_id, 0) = ? AND item_code = ?""",
                    (document_id, sec["id"], it["item_code"]),
                ).fetchone()

                if existing:
                    skipped += 1
                    continue

                # Phase 2: 체크포인트 기반 충족 수준 정밀 평가
                assessment = assess_fulfillment(
                    section_content=sec_text,
                    item_code=it["item_code"],
                    doc_type=doc_type,
                    conn=conn,
                )

                coverage = assessment.coverage_level
                notes = assessment.summary_text()
                assessment_counts[coverage] = assessment_counts.get(coverage, 0) + 1

                # confidence_score는 _compute_relevance_score()가 계산한 값을 사용
                cursor = conn.execute(
                    """INSERT INTO document_item_mappings
                       (document_id, section_id, item_code, fulfillment_type,
                        coverage_level, confidence_score, mapping_source, verified, notes)
                       VALUES (?, ?, ?, 'document', ?, ?, 'auto_keyword', 0, ?)""",
                    (document_id, sec["id"], it["item_code"], coverage, round(relevance, 3), notes),
                )
                _log_mapping(
                    conn, "auto_suggest", cursor.lastrowid,
                    document_id, it["item_code"],
                    f"자동 매핑+평가 ({coverage}, score={relevance:.3f}, section={sec['section_number']})",
                )
                suggestions += 1

    conn.commit()
    conn.close()
    return {"suggestions": suggestions, "skipped": skipped, "assessment": assessment_counts, "error": None}
