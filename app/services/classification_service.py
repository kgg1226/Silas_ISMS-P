"""
ISMS-P 통제항목 충족유형 자동 분류 서비스

101개 항목의 evidence_examples + key_checks를 분석하여
document / system / mixed로 분류하고 item_fulfillment_types에 저장.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))

# ---------------------------------------------------------------------------
# 키워드 사전
# ---------------------------------------------------------------------------
DOC_KEYWORDS = [
    "정책", "지침", "절차", "계획", "문서", "규정", "보고", "기록",
    "매뉴얼", "회의록", "목록", "명세", "조직도", "계약서", "양식",
    "내부 관리계획", "점검표", "대장", "서약서", "협약서", "개인정보 처리방침",
    "약관", "동의서", "통지", "고지", "공개", "수립", "마련",
]

SYS_KEYWORDS = [
    "로그", "스크린샷", "화면", "설정", "구성도", "모니터링",
    "시스템", "네트워크", "서버", "접속기록", "백업", "패치",
    "취약점", "진단", "스캔", "탐지", "차단", "암호화",
    "인증", "접근통제", "방화벽", "IDS", "IPS",
]


def _parse_json_list(raw: Optional[str]) -> list[str]:
    """JSON 배열 문자열을 리스트로 파싱."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return [raw] if raw and raw.strip() else []


def classify_item(
    evidence_examples: list[str],
    key_checks: list[str],
) -> tuple[str, float]:
    """
    항목의 증적 예시와 주요 확인사항을 분석하여 충족유형 분류.

    Returns:
        (fulfillment_type, confidence)
        - fulfillment_type: 'document' | 'system' | 'mixed'
        - confidence: 0.0 ~ 1.0
    """
    all_items = evidence_examples + key_checks
    if not all_items:
        return ("document", 0.5)

    doc_count = 0
    sys_count = 0

    for item_text in all_items:
        has_doc = any(kw in item_text for kw in DOC_KEYWORDS)
        has_sys = any(kw in item_text for kw in SYS_KEYWORDS)

        if has_doc:
            doc_count += 1
        if has_sys:
            sys_count += 1

    total = len(all_items) or 1
    doc_ratio = doc_count / total
    sys_ratio = sys_count / total

    # 분류 로직
    if doc_ratio >= 0.5 and sys_ratio < 0.2:
        return ("document", round(doc_ratio, 3))
    elif sys_ratio >= 0.5 and doc_ratio < 0.2:
        return ("system", round(sys_ratio, 3))
    elif doc_ratio >= 0.3 and sys_ratio >= 0.2:
        return ("mixed", round(max(doc_ratio, sys_ratio), 3))
    elif sys_ratio >= 0.3 and doc_ratio >= 0.2:
        return ("mixed", round(max(doc_ratio, sys_ratio), 3))
    elif doc_ratio > sys_ratio:
        return ("document", round(doc_ratio, 3))
    elif sys_ratio > doc_ratio:
        return ("system", round(sys_ratio, 3))
    else:
        return ("document", 0.5)


def classify_all_items() -> dict:
    """
    DB의 101개 항목을 모두 분류하여 item_fulfillment_types에 저장.

    Returns:
        {"total": int, "document": int, "system": int, "mixed": int}
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # item_fulfillment_types 테이블 존재 확인
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='item_fulfillment_types'"
    ).fetchone()
    if not table_exists:
        raise RuntimeError(
            "item_fulfillment_types 테이블이 없습니다. "
            "먼저 database/migrate_v2_documents.py를 실행하세요."
        )

    # 전체 항목 로드
    rows = conn.execute(
        "SELECT item_code, evidence_examples, key_checks FROM isms_requirements ORDER BY item_code"
    ).fetchall()

    stats = {"total": 0, "document": 0, "system": 0, "mixed": 0}

    for row in rows:
        item_code = row["item_code"]
        evidence_examples = _parse_json_list(row["evidence_examples"])
        key_checks = _parse_json_list(row["key_checks"])

        ftype, confidence = classify_item(evidence_examples, key_checks)
        stats["total"] += 1
        stats[ftype] += 1

        # UPSERT
        conn.execute(
            """INSERT INTO item_fulfillment_types
               (item_code, fulfillment_type, auto_classified, confidence, classified_by)
               VALUES (?, ?, 1, ?, 'system')
               ON CONFLICT(item_code) DO UPDATE SET
                 fulfillment_type = excluded.fulfillment_type,
                 auto_classified = 1,
                 confidence = excluded.confidence,
                 classified_at = datetime('now'),
                 classified_by = 'system'
            """,
            (item_code, ftype, confidence),
        )

    conn.commit()
    conn.close()

    return stats


def get_fulfillment_type(item_code: str) -> Optional[str]:
    """단일 항목의 충족유형 조회."""
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute(
        "SELECT fulfillment_type FROM item_fulfillment_types WHERE item_code = ?",
        (item_code,),
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_fulfillment_summary() -> dict:
    """전체 분류 현황 요약."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT fulfillment_type, COUNT(*) as cnt
           FROM item_fulfillment_types
           GROUP BY fulfillment_type
           ORDER BY fulfillment_type"""
    ).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM item_fulfillment_types").fetchone()[0]
    conn.close()

    result = {"total": total, "document": 0, "system": 0, "mixed": 0}
    for r in rows:
        result[r["fulfillment_type"]] = r["cnt"]

    return result


if __name__ == "__main__":
    print("ISMS-P 통제항목 충족유형 분류 시작...")
    stats = classify_all_items()
    print(f"\n분류 완료:")
    print(f"  전체: {stats['total']}개")
    print(f"  문서형 (document): {stats['document']}개")
    print(f"  시스템형 (system): {stats['system']}개")
    print(f"  복합형 (mixed): {stats['mixed']}개")

    # 상세 목록 출력
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT f.item_code, f.fulfillment_type, f.confidence,
                  r.item_title
           FROM item_fulfillment_types f
           JOIN isms_requirements r ON f.item_code = r.item_code
           ORDER BY f.fulfillment_type, f.item_code"""
    ).fetchall()
    conn.close()

    current_type = ""
    for r in rows:
        if r["fulfillment_type"] != current_type:
            current_type = r["fulfillment_type"]
            label = {"document": "문서형", "system": "시스템형", "mixed": "복합형"}
            print(f"\n=== {label.get(current_type, current_type)} ===")
        print(f"  {r['item_code']} {r['item_title']} (신뢰도: {r['confidence']:.2f})")
