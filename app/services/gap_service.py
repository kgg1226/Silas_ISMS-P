"""
갭 분석 서비스 — 101개 항목의 충족 현황 분석
"""

from __future__ import annotations

import csv
import io
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_gap_analysis(chapter_filter: str = "") -> dict:
    """
    전체 갭 분석 수행.

    Returns:
        {
            "summary": {"total", "fulfilled", "partial", "unverified", "gap", "expiring"},
            "sections": [{"section", "section_title", "items": [...]}],
            "items": [{item_code, item_title, gap_status, ...}],
        }
    """
    conn = _get_conn()

    query = """
        SELECT
            r.item_code,
            r.item_title,
            r.chapter,
            r.section,
            r.section_title,
            COALESCE(ft.fulfillment_type, 'unclassified') AS fulfillment_type,
            COUNT(DISTINCT CASE WHEN m.verified = 1 AND m.coverage_level = 'full' THEN m.id END) AS full_count,
            COUNT(DISTINCT CASE WHEN m.verified = 1 AND m.coverage_level IN ('partial','reference') THEN m.id END) AS partial_count,
            COUNT(DISTINCT CASE WHEN m.verified = 0 THEN m.id END) AS unverified_count,
            COUNT(DISTINCT m.document_id) AS linked_docs,
            MIN(CASE WHEN d.status = 'active' AND d.expiry_date IS NOT NULL THEN d.expiry_date END) AS earliest_expiry
        FROM isms_requirements r
        LEFT JOIN item_fulfillment_types ft ON r.item_code = ft.item_code
        LEFT JOIN document_item_mappings m ON r.item_code = m.item_code
        LEFT JOIN documents d ON m.document_id = d.id
    """
    params = []
    if chapter_filter:
        query += " WHERE r.chapter = ?"
        params.append(chapter_filter)

    query += " GROUP BY r.item_code ORDER BY r.item_code"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    # 갭 상태 계산
    today = datetime.now().strftime("%Y-%m-%d")
    expiry_threshold = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    summary = {"total": 0, "fulfilled": 0, "partial": 0, "unverified": 0, "gap": 0, "expiring": 0}
    items = []
    sections_dict: dict[str, dict] = {}

    for r in rows:
        item = dict(r)
        summary["total"] += 1

        # 갭 상태 결정
        if r["full_count"] > 0:
            item["gap_status"] = "fulfilled"
            summary["fulfilled"] += 1
        elif r["partial_count"] > 0:
            item["gap_status"] = "partial"
            summary["partial"] += 1
        elif r["unverified_count"] > 0:
            item["gap_status"] = "unverified"
            summary["unverified"] += 1
        else:
            item["gap_status"] = "gap"
            summary["gap"] += 1

        # 만료 임박 체크
        if r["earliest_expiry"] and r["earliest_expiry"] <= expiry_threshold:
            item["expiring"] = True
            if r["earliest_expiry"] < today:
                item["expired"] = True
            summary["expiring"] += 1
        else:
            item["expiring"] = False
            item["expired"] = False

        items.append(item)

        # 섹션별 그룹핑
        sec_key = r["section"]
        if sec_key not in sections_dict:
            sections_dict[sec_key] = {
                "section": sec_key,
                "section_title": r["section_title"],
                "chapter": r["chapter"],
                "items": [],
                "fulfilled": 0,
                "partial": 0,
                "gap": 0,
            }
        sections_dict[sec_key]["items"].append(item)
        if item["gap_status"] == "fulfilled":
            sections_dict[sec_key]["fulfilled"] += 1
        elif item["gap_status"] in ("partial", "unverified"):
            sections_dict[sec_key]["partial"] += 1
        else:
            sections_dict[sec_key]["gap"] += 1

    sections = sorted(sections_dict.values(), key=lambda x: x["section"])

    return {
        "summary": summary,
        "sections": sections,
        "items": items,
    }


def export_gap_csv() -> str:
    """갭 분석 결과를 CSV 문자열로 반환."""
    analysis = get_gap_analysis()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "항목코드", "항목명", "장", "절", "절명",
        "충족유형", "갭상태", "검증매핑", "미검증매핑", "연결문서", "최근만료일",
    ])

    for item in analysis["items"]:
        writer.writerow([
            item["item_code"],
            item["item_title"],
            item["chapter"],
            item["section"],
            item["section_title"],
            item["fulfillment_type"],
            item["gap_status"],
            item["full_count"] + item["partial_count"],
            item["unverified_count"],
            item["linked_docs"],
            item.get("earliest_expiry", ""),
        ])

    return output.getvalue()
