"""공통 pytest fixture — 임시 DB + TestClient."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def temp_db_path(tmp_path_factory) -> Path:
    """세션 단위 임시 DB 경로."""
    tmp_dir = tmp_path_factory.mktemp("isms_test_db")
    db_path = tmp_dir / "isms_p.db"
    os.environ["ISMS_DB_PATH"] = str(db_path)
    os.environ["DB_PATH"] = str(db_path)
    return db_path


@pytest.fixture(scope="session")
def initialized_db(temp_db_path: Path) -> Path:
    """스키마가 초기화된 임시 DB.

    init_db는 모듈 레벨 DB_PATH 상수를 쓰기 때문에
    환경변수를 세팅한 뒤 임포트해야 한다.
    """
    # temp_db_path fixture에서 이미 환경변수 설정됨
    import importlib
    import database.init_db as init_module
    importlib.reload(init_module)
    init_module.init_database()

    # 문서 관리 마이그레이션도 적용
    import database.migrate_v2_documents as mig
    importlib.reload(mig)
    mig.migrate_v2()

    return temp_db_path


@pytest.fixture
def db_conn(initialized_db: Path):
    """각 테스트마다 새 연결."""
    conn = sqlite3.connect(str(initialized_db))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def test_client(initialized_db: Path):
    """FastAPI TestClient (lifespan 스케줄러 비활성)."""
    from fastapi.testclient import TestClient

    # APScheduler가 테스트 중 실행되지 않도록 환경변수로 분기하기 어려우므로
    # 앱을 직접 임포트하되 스케줄러는 무시
    from app.main import app
    with TestClient(app) as client:
        yield client
