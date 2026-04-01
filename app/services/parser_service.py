"""
문서 파싱 오케스트레이터

문서 파일을 파싱하여 document_sections 테이블에 저장.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

from parsers.combined_parser import parse_document
from parsers.section_detector import Section

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def parse_document_by_id(doc_id: int) -> dict:
    """
    문서 ID로 파싱 실행.

    Returns:
        {"success": bool, "sections_count": int, "error": str | None}
    """
    conn = _get_conn()

    # 문서 정보 로드
    doc = conn.execute(
        "SELECT file_path, mime_type, parse_status FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()

    if not doc:
        conn.close()
        return {"success": False, "sections_count": 0, "error": "문서를 찾을 수 없습니다."}

    # 파일 경로
    file_path = UPLOADS_DIR / doc["file_path"]
    if not file_path.exists():
        conn.execute(
            "UPDATE documents SET parse_status = 'failed', parse_error = ? WHERE id = ?",
            ("파일을 찾을 수 없습니다.", doc_id),
        )
        conn.commit()
        conn.close()
        return {"success": False, "sections_count": 0, "error": "파일을 찾을 수 없습니다."}

    # 파싱 상태 업데이트
    conn.execute(
        "UPDATE documents SET parse_status = 'parsing' WHERE id = ?", (doc_id,)
    )
    conn.commit()

    # 파싱 실행
    sections, total_pages, error = parse_document(file_path)

    if error:
        # unsupported 형식인지 확인
        parse_status = "unsupported" if "지원하지 않는" in error or "Unsupported" in error else "failed"
        conn.execute(
            "UPDATE documents SET parse_status = ?, parse_error = ?, total_pages = ? WHERE id = ?",
            (parse_status, error, total_pages, doc_id),
        )
        conn.commit()
        conn.close()
        return {"success": False, "sections_count": 0, "error": error}

    # 기존 섹션 삭제 (재파싱 시)
    conn.execute("DELETE FROM document_sections WHERE document_id = ?", (doc_id,))

    # 섹션 저장
    section_count = _save_sections(conn, doc_id, sections, parent_id=None)

    # 문서 메타 업데이트
    conn.execute(
        """UPDATE documents SET
           parse_status = 'completed',
           parse_error = NULL,
           total_pages = ?,
           total_sections = ?,
           updated_at = datetime('now')
           WHERE id = ?""",
        (total_pages, section_count, doc_id),
    )
    conn.commit()
    conn.close()

    return {"success": True, "sections_count": section_count, "error": None}


def _save_sections(
    conn: sqlite3.Connection,
    doc_id: int,
    sections: list[Section],
    parent_id: Optional[int],
) -> int:
    """섹션을 재귀적으로 DB에 저장. 저장된 총 개수 반환."""
    count = 0

    for sec in sections:
        cursor = conn.execute(
            """INSERT INTO document_sections
               (document_id, parent_id, section_number, section_title,
                content, page_start, page_end, depth, sort_order, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc_id,
                parent_id,
                sec.section_number,
                sec.section_title,
                sec.content,
                sec.page_start,
                sec.page_end,
                sec.depth,
                sec.sort_order,
                sec.content_hash,
            ),
        )
        section_id = cursor.lastrowid
        count += 1

        # 하위 섹션 저장
        if sec.children:
            count += _save_sections(conn, doc_id, sec.children, section_id)

    return count
