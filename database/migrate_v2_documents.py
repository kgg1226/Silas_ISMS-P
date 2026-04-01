"""
ISMS-P 문서 매핑 시스템 DB 마이그레이션 v2
6개 신규 테이블 생성 (기존 테이블 변경 없음, 멱등 실행)
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))

V2_SCHEMA = """
PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. item_fulfillment_types: 항목별 충족유형 분류
-- ============================================================
CREATE TABLE IF NOT EXISTS item_fulfillment_types (
    item_code        TEXT PRIMARY KEY,
    fulfillment_type TEXT NOT NULL DEFAULT 'document'
                     CHECK (fulfillment_type IN ('document', 'system', 'mixed')),
    auto_classified  INTEGER NOT NULL DEFAULT 1,
    confidence       REAL DEFAULT 0.0,
    classified_at    TEXT DEFAULT (datetime('now')),
    classified_by    TEXT DEFAULT 'system',
    notes            TEXT,
    FOREIGN KEY (item_code) REFERENCES isms_requirements(item_code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ift_type ON item_fulfillment_types(fulfillment_type);

-- ============================================================
-- 2. documents: 업로드 문서 관리
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    doc_type        TEXT NOT NULL
                    CHECK (doc_type IN ('정책서','지침서','절차서','계획서','보고서','회의록','승인문서','매뉴얼','기타')),
    file_name       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_size       INTEGER,
    file_hash       TEXT,
    mime_type       TEXT,
    version         TEXT NOT NULL DEFAULT '1.0',
    author          TEXT,
    approver        TEXT,
    approval_date   TEXT,
    effective_date  TEXT,
    expiry_date     TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('draft','active','expired','superseded','archived')),
    description     TEXT,
    total_pages     INTEGER,
    total_sections  INTEGER DEFAULT 0,
    parse_status    TEXT DEFAULT 'pending'
                    CHECK (parse_status IN ('pending','parsing','completed','failed','unsupported')),
    parse_error     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    created_by      TEXT DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_doc_status  ON documents(status);
CREATE INDEX IF NOT EXISTS idx_doc_type    ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_doc_expiry  ON documents(expiry_date);
CREATE INDEX IF NOT EXISTS idx_doc_hash    ON documents(file_hash);

-- ============================================================
-- 3. document_versions: 문서 버전 이력
-- ============================================================
CREATE TABLE IF NOT EXISTS document_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL,
    version         TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_hash       TEXT,
    change_summary  TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    created_by      TEXT DEFAULT 'system',
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_docver_doc ON document_versions(document_id);

-- ============================================================
-- 4. document_sections: 문서 조항 단위 파싱
-- ============================================================
CREATE TABLE IF NOT EXISTS document_sections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL,
    parent_id       INTEGER,
    section_number  TEXT NOT NULL,
    section_title   TEXT,
    content         TEXT,
    page_start      INTEGER,
    page_end        INTEGER,
    depth           INTEGER NOT NULL DEFAULT 0,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    content_hash    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES document_sections(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_docsec_doc    ON document_sections(document_id);
CREATE INDEX IF NOT EXISTS idx_docsec_parent ON document_sections(parent_id);
CREATE INDEX IF NOT EXISTS idx_docsec_num    ON document_sections(section_number);

-- ============================================================
-- 5. document_item_mappings: 문서-항목 N:M 매핑
-- ============================================================
CREATE TABLE IF NOT EXISTS document_item_mappings (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id      INTEGER NOT NULL,
    section_id       INTEGER,
    item_code        TEXT NOT NULL,
    fulfillment_type TEXT NOT NULL DEFAULT 'document'
                     CHECK (fulfillment_type IN ('document', 'system', 'mixed')),
    coverage_level   TEXT NOT NULL DEFAULT 'partial'
                     CHECK (coverage_level IN ('full', 'partial', 'reference')),
    confidence_score REAL DEFAULT 0.0,
    mapping_source   TEXT NOT NULL DEFAULT 'manual'
                     CHECK (mapping_source IN ('manual', 'auto_keyword', 'auto_embedding', 'imported')),
    verified         INTEGER NOT NULL DEFAULT 0,
    verified_by      TEXT,
    verified_at      TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    created_by       TEXT DEFAULT 'system',
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES document_sections(id) ON DELETE SET NULL,
    FOREIGN KEY (item_code) REFERENCES isms_requirements(item_code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dim_doc      ON document_item_mappings(document_id);
CREATE INDEX IF NOT EXISTS idx_dim_section  ON document_item_mappings(section_id);
CREATE INDEX IF NOT EXISTS idx_dim_item     ON document_item_mappings(item_code);
CREATE INDEX IF NOT EXISTS idx_dim_verified ON document_item_mappings(verified);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_unique
    ON document_item_mappings(document_id, COALESCE(section_id, 0), item_code);

-- ============================================================
-- 6. mapping_logs: 매핑 감사 로그
-- ============================================================
CREATE TABLE IF NOT EXISTS mapping_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,
    mapping_id  INTEGER,
    document_id INTEGER,
    item_code   TEXT,
    detail      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    created_by  TEXT DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_maplog_action ON mapping_logs(action, created_at);
CREATE INDEX IF NOT EXISTS idx_maplog_doc    ON mapping_logs(document_id);

-- ============================================================
-- Triggers: updated_at 자동 갱신
-- ============================================================
CREATE TRIGGER IF NOT EXISTS trg_doc_updated_at
AFTER UPDATE ON documents
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE documents SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_dim_updated_at
AFTER UPDATE ON document_item_mappings
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE document_item_mappings SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

REQUIRED_TABLES = [
    "item_fulfillment_types",
    "documents",
    "document_versions",
    "document_sections",
    "document_item_mappings",
    "mapping_logs",
]


def migrate_v2(conn: sqlite3.Connection | None = None):
    """문서 매핑 시스템 테이블 생성. 멱등 실행."""
    close = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        close = True

    conn.executescript(V2_SCHEMA)

    # 검증
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]
    missing = [t for t in REQUIRED_TABLES if t not in tables]
    if missing:
        raise RuntimeError(f"마이그레이션 불완전. 누락 테이블: {missing}")

    if close:
        conn.close()

    return True


def backup_and_migrate():
    """백업 후 마이그레이션 실행."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.parent / f"isms_p.db.bak.v2.{ts}"
    shutil.copy2(str(DB_PATH), str(backup_path))
    print(f"백업: {backup_path}")

    migrate_v2()
    print(f"마이그레이션 완료: {len(REQUIRED_TABLES)}개 테이블 생성/확인")


if __name__ == "__main__":
    backup_and_migrate()

    # 검증 출력
    conn = sqlite3.connect(str(DB_PATH))
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]
    print(f"\n전체 테이블 ({len(tables)}개):")
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        print(f"  {t}: {count}건")
    conn.close()
