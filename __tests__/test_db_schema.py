"""DB 스키마 초기화 검증."""
from __future__ import annotations


REQUIRED_TABLES = {
    "isms_requirements",
    "evidences",
    "evidence_logs",
    "law_versions",
    "law_sync_logs",
    "isms_sync_logs",
}


def test_core_tables_exist(db_conn):
    cur = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    names = {r[0] for r in cur.fetchall()}
    missing = REQUIRED_TABLES - names
    assert not missing, f"누락된 테이블: {missing}"


def test_isms_requirements_columns(db_conn):
    cur = db_conn.execute("PRAGMA table_info(isms_requirements)")
    cols = {r[1] for r in cur.fetchall()}
    required = {
        "item_code",
        "item_title",
        "section",
        "section_title",
        "certification_criteria",
        "key_checks",
        "evidence_examples",
        "related_laws",
    }
    assert required.issubset(cols), f"누락 컬럼: {required - cols}"


def test_law_versions_unique_constraint(db_conn):
    db_conn.execute(
        "INSERT INTO law_versions (law_name, status) VALUES (?, 'active')",
        ("개인정보 보호법",),
    )
    db_conn.commit()
    # 중복 삽입 시 에러
    import sqlite3
    try:
        db_conn.execute(
            "INSERT INTO law_versions (law_name, status) VALUES (?, 'active')",
            ("개인정보 보호법",),
        )
        db_conn.commit()
        assert False, "UNIQUE 제약이 작동하지 않음"
    except sqlite3.IntegrityError:
        pass
    finally:
        db_conn.execute("DELETE FROM law_versions WHERE law_name = ?", ("개인정보 보호법",))
        db_conn.commit()
