"""
문서 업로드, 저장, 메타데이터 관리 서비스
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024  # bytes

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".hwp", ".hwpx"}
MIME_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".hwp": "application/x-hwp",
    ".hwpx": "application/x-hwpx",
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _sanitize_filename(name: str) -> str:
    """파일명에서 위험 문자 제거 (한글 보존)."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name)
    return name[:100]


def _compute_hash(data: bytes) -> str:
    """SHA-256 해시 계산."""
    return hashlib.sha256(data).hexdigest()


def _generate_path(filename: str) -> tuple[str, str]:
    """
    저장 경로 생성: data/uploads/{YYYY}/{MM}/{uuid8}_{sanitized}
    Returns: (relative_path, absolute_path)
    """
    now = datetime.now()
    uid = uuid.uuid4().hex[:8]
    safe_name = _sanitize_filename(filename)
    rel_dir = f"{now.year}/{now.month:02d}"
    rel_path = f"{rel_dir}/{uid}_{safe_name}"
    abs_path = UPLOADS_DIR / rel_path

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    return rel_path, str(abs_path)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def upload_document(
    file_data: bytes,
    file_name: str,
    title: str,
    doc_type: str,
    version: str = "1.0",
    author: str = "",
    approver: str = "",
    approval_date: str = "",
    effective_date: str = "",
    expiry_date: str = "",
    description: str = "",
    created_by: str = "system",
) -> dict:
    """
    문서 업로드: 파일 저장 + DB 레코드 생성.
    Returns: {"success": bool, "doc_id": int | None, "error": str | None}
    """
    # 1. 확장자 검증
    ext = Path(file_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"success": False, "doc_id": None, "error": f"지원하지 않는 형식: {ext}"}

    # 2. 크기 검증
    if len(file_data) > MAX_UPLOAD_SIZE:
        mb = MAX_UPLOAD_SIZE // (1024 * 1024)
        return {"success": False, "doc_id": None, "error": f"파일 크기 초과 (최대 {mb}MB)"}

    # 3. 해시 계산 + 중복 확인
    file_hash = _compute_hash(file_data)
    conn = _get_conn()
    dup = conn.execute(
        "SELECT id, title, version FROM documents WHERE file_hash = ? AND status != 'archived'",
        (file_hash,),
    ).fetchone()
    if dup:
        conn.close()
        return {
            "success": False,
            "doc_id": dup["id"],
            "error": f"동일 파일 존재: '{dup['title']}' (v{dup['version']}, ID: {dup['id']})",
        }

    # 4. 파일 저장
    rel_path, abs_path = _generate_path(file_name)
    with open(abs_path, "wb") as f:
        f.write(file_data)

    # 5. DB 레코드 생성
    mime = MIME_MAP.get(ext, "application/octet-stream")
    cursor = conn.execute(
        """INSERT INTO documents
           (title, doc_type, file_name, file_path, file_size, file_hash,
            mime_type, version, author, approver, approval_date,
            effective_date, expiry_date, status, description, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
        (
            title, doc_type, file_name, rel_path, len(file_data), file_hash,
            mime, version, author, approver, approval_date,
            effective_date, expiry_date, description, created_by,
        ),
    )
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {"success": True, "doc_id": doc_id, "error": None}


def get_document(doc_id: int) -> Optional[dict]:
    """문서 상세 조회."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_document_list(
    status: str = "",
    doc_type: str = "",
    search: str = "",
) -> list[dict]:
    """문서 목록 조회 (필터 지원)."""
    conn = _get_conn()
    query = "SELECT * FROM documents WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if doc_type:
        query += " AND doc_type = ?"
        params.append(doc_type)
    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR file_name LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])

    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document_stats() -> dict:
    """문서 통계."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM documents WHERE status='active'").fetchone()[0]
    expired = conn.execute("SELECT COUNT(*) FROM documents WHERE status='expired'").fetchone()[0]
    pending_parse = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE parse_status='pending'"
    ).fetchone()[0]
    conn.close()
    return {
        "total": total,
        "active": active,
        "expired": expired,
        "pending_parse": pending_parse,
    }


def update_document_status(doc_id: int, new_status: str) -> bool:
    """문서 상태 변경."""
    valid = {"draft", "active", "expired", "superseded", "archived"}
    if new_status not in valid:
        return False
    conn = _get_conn()
    conn.execute(
        "UPDATE documents SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, doc_id),
    )
    conn.commit()
    conn.close()
    return True


def get_document_sections(doc_id: int) -> list[dict]:
    """문서의 파싱된 섹션 목록."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT * FROM document_sections
           WHERE document_id = ?
           ORDER BY sort_order, id""",
        (doc_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document_mappings(doc_id: int) -> list[dict]:
    """문서에 연결된 매핑 목록."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT m.*, r.item_title, r.section_title,
                  s.section_number, s.section_title as sec_title
           FROM document_item_mappings m
           JOIN isms_requirements r ON m.item_code = r.item_code
           LEFT JOIN document_sections s ON m.section_id = s.id
           WHERE m.document_id = ?
           ORDER BY m.item_code""",
        (doc_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_file_path(doc_id: int) -> Optional[str]:
    """문서의 실제 파일 경로 반환."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT file_path FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return str(UPLOADS_DIR / row["file_path"])


# ---------------------------------------------------------------------------
# 버전 관리 (Phase 7)
# ---------------------------------------------------------------------------

def upload_new_version(
    doc_id: int,
    file_data: bytes,
    file_name: str,
    new_version: str,
    change_summary: str = "",
    created_by: str = "system",
) -> dict:
    """
    기존 문서의 새 버전 업로드.
    1. 기존 파일 → document_versions에 아카이브
    2. 새 파일 업로드
    3. 기존 매핑 verified=0으로 리셋
    """
    conn = _get_conn()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        return {"success": False, "error": "문서를 찾을 수 없습니다."}

    ext = Path(file_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        conn.close()
        return {"success": False, "error": f"지원하지 않는 형식: {ext}"}

    # 1. 기존 버전 아카이브
    conn.execute(
        """INSERT INTO document_versions
           (document_id, version, file_path, file_hash, change_summary, created_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (doc_id, doc["version"], doc["file_path"], doc["file_hash"],
         change_summary, created_by),
    )

    # 2. 새 파일 저장
    file_hash = _compute_hash(file_data)
    rel_path, abs_path = _generate_path(file_name)
    with open(abs_path, "wb") as f:
        f.write(file_data)

    mime = MIME_MAP.get(ext, "application/octet-stream")

    # 3. 문서 레코드 갱신
    conn.execute(
        """UPDATE documents SET
           file_name = ?, file_path = ?, file_size = ?, file_hash = ?,
           mime_type = ?, version = ?, parse_status = 'pending',
           parse_error = NULL, total_sections = 0,
           updated_at = datetime('now')
           WHERE id = ?""",
        (file_name, rel_path, len(file_data), file_hash, mime, new_version, doc_id),
    )

    # 4. 기존 매핑 재검증 필요 표시
    conn.execute(
        "UPDATE document_item_mappings SET verified = 0, verified_at = NULL WHERE document_id = ?",
        (doc_id,),
    )

    # 5. 기존 섹션 삭제 (재파싱 필요)
    conn.execute("DELETE FROM document_sections WHERE document_id = ?", (doc_id,))

    conn.commit()
    conn.close()
    return {"success": True, "error": None}


def get_document_versions(doc_id: int) -> list[dict]:
    """문서 버전 이력 조회."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT * FROM document_versions
           WHERE document_id = ? ORDER BY created_at DESC""",
        (doc_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def expire_documents() -> int:
    """만료일이 지난 문서를 자동으로 expired 상태로 변경. 변경 건수 반환."""
    conn = _get_conn()
    cursor = conn.execute(
        """UPDATE documents SET status = 'expired', updated_at = datetime('now')
           WHERE status = 'active' AND expiry_date IS NOT NULL
           AND date(expiry_date) < date('now')"""
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def get_expiring_documents(days: int = 30) -> list[dict]:
    """만료 임박 문서 목록."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT * FROM documents
           WHERE status = 'active' AND expiry_date IS NOT NULL
           AND date(expiry_date) <= date('now', '+' || ? || ' days')
           ORDER BY expiry_date""",
        (days,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
