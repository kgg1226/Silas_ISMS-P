#!/usr/bin/env python3
"""
ISMS-P 데이터베이스 초기화/마이그레이션 스크립트

실제 DB 스키마 (data/isms_p.db):
  - isms_requirements: 20컬럼 (chapter, section, section_title, item_code,
    item_title, certification_criteria, key_checks, detailed_explanation,
    evidence_examples, related_laws, defect_cases, notes, description,
    title, category, requirement, control_objective, ...)
  - evidences: (id, item_code, evidence_type, content, status, created_at)
  - evidence_logs: (id, item_code, evidence_type, content, created_at, created_by)

사용법:
  python database/init_db.py           # 기본 경로(data/isms_p.db)
  DB_PATH=path/to/db python database/init_db.py  # 커스텀 경로
"""

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", "data/isms_p.db")))

SCHEMA = """
PRAGMA foreign_keys = ON;

-- 요구사항 (ISMS-P 인증기준 101개 항목)
CREATE TABLE IF NOT EXISTS isms_requirements (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter                TEXT NOT NULL,           -- 장 (1, 2, 3)
    section                TEXT NOT NULL,           -- 절 (1.1, 2.5, 3.2)
    section_title          TEXT NOT NULL,           -- 절 제목
    item_code              TEXT NOT NULL UNIQUE,    -- 항목코드 (1.1.1)
    item_title             TEXT NOT NULL,           -- 항목명
    certification_criteria TEXT NOT NULL,           -- 인증기준
    key_checks             TEXT,                    -- 주요 확인사항 (JSON 배열)
    detailed_explanation   TEXT,                    -- 세부 설명 (JSON 배열)
    evidence_examples      TEXT,                    -- 증적 예시 (JSON 배열)
    related_laws           TEXT,                    -- 관련 법령 (JSON 배열)
    defect_cases           TEXT,                    -- 결함 사례 (JSON 배열)
    notes                  TEXT,                    -- 비고
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 호환성 필드 (MCP 서버에서 편의용으로 사용)
    description            TEXT,                    -- = certification_criteria
    title                  TEXT,                    -- = item_title
    category               TEXT,                    -- = section_title
    requirement            TEXT,                    -- = certification_criteria
    control_objective      TEXT                     -- 통제 목표
);

-- 증적 (MCP 서버에서 사용)
CREATE TABLE IF NOT EXISTS evidences (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code     TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    content       TEXT NOT NULL,
    status        TEXT DEFAULT 'completed' CHECK (status IN ('pending','completed','rejected')),
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (item_code) REFERENCES isms_requirements(item_code) ON DELETE CASCADE
);

-- 증적 로그 (레거시 호환)
CREATE TABLE IF NOT EXISTS evidence_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code     TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    content       TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by    TEXT DEFAULT 'system',
    FOREIGN KEY (item_code) REFERENCES isms_requirements(item_code) ON DELETE CASCADE
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_req_item_code  ON isms_requirements(item_code);
CREATE INDEX IF NOT EXISTS idx_req_chapter    ON isms_requirements(chapter);
CREATE INDEX IF NOT EXISTS idx_req_section    ON isms_requirements(section);
CREATE INDEX IF NOT EXISTS idx_ev_item_code   ON evidences(item_code);
CREATE INDEX IF NOT EXISTS idx_evlog_item     ON evidence_logs(item_code);

-- updated_at 자동 갱신 트리거
CREATE TRIGGER IF NOT EXISTS trg_req_updated_at
AFTER UPDATE ON isms_requirements
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE isms_requirements SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- 법령 버전 추적 (법제처 API 연동)
CREATE TABLE IF NOT EXISTS law_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    law_name        TEXT NOT NULL,
    law_name_short  TEXT,
    law_mst         TEXT,
    law_type        TEXT,
    current_version TEXT,
    amendment_date  TEXT,
    amendment_type  TEXT,
    previous_version TEXT,
    status          TEXT DEFAULT 'active'
                    CHECK (status IN ('active','amended','deprecated','unknown')),
    last_synced     TEXT,
    sync_result     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(law_name)
);

-- 법령 동기화 로그
CREATE TABLE IF NOT EXISTS law_sync_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    law_name    TEXT NOT NULL,
    event       TEXT NOT NULL,
    detail      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_law_ver_name   ON law_versions(law_name);
CREATE INDEX IF NOT EXISTS idx_law_ver_status ON law_versions(status);
CREATE INDEX IF NOT EXISTS idx_law_sync_log   ON law_sync_logs(law_name, created_at);

-- ISMS-P 인증기준 동기화 로그
CREATE TABLE IF NOT EXISTS isms_sync_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code  TEXT,
    field      TEXT,
    event      TEXT NOT NULL,       -- version_check / change_detected / change_check / manual_update
    source     TEXT,                -- kisa_pdf / meganad_github / manual
    detail     TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_isms_sync_event ON isms_sync_logs(event, created_at);
CREATE INDEX IF NOT EXISTS idx_isms_sync_item  ON isms_sync_logs(item_code);
"""


def init_database():
    """DB 파일이 없으면 스키마 생성. 이미 있으면 누락 테이블만 보완."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)

        # 현황 출력
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [r[0] for r in cur.fetchall()]
        print(f"📋 테이블: {', '.join(tables)}")

        cur = conn.execute("SELECT COUNT(*) FROM isms_requirements")
        count = cur.fetchone()[0]
        print(f"📊 인증기준 항목: {count}개")

        if count > 0:
            for row in conn.execute(
                "SELECT item_code, item_title FROM isms_requirements ORDER BY item_code LIMIT 5"
            ):
                print(f"   - {row[0]}: {row[1]}")

        cur = conn.execute("SELECT COUNT(*) FROM evidences")
        ev_count = cur.fetchone()[0]
        print(f"📎 증적: {ev_count}건")

    print(f"\n📍 Database: {DB_PATH.resolve()}")
    print("✅ 초기화 완료")


if __name__ == "__main__":
    init_database()
