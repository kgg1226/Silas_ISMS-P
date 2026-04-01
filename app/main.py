"""
ISMS-P 문서 관리 웹 — FastAPI + Jinja2
문서 관련 통제 항목 27건을 관리하는 웹 대시보드.
법령 자동 최신화 스케줄러 포함.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logger = logging.getLogger("isms-web")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ---------------------------------------------------------------------------
# Scheduler: 법령 자동 최신화 (주 1회)
# ---------------------------------------------------------------------------
_scheduler = None

def _start_law_scheduler():
    """APScheduler 사용 가능하면 주간 동기화 스케줄 등록."""
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from app.law_sync import sync_all_laws, init_tracked_laws

        init_tracked_laws()  # 추적 법령 테이블 초기화

        _scheduler = BackgroundScheduler(timezone="Asia/Seoul")
        # 매주 월요일 09:00 동기화
        _scheduler.add_job(
            sync_all_laws,
            trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
            id="law_sync_weekly",
            name="법령 주간 동기화",
            replace_existing=True,
        )

        # 문서 만료 자동 체크 (매일 08:00)
        try:
            from app.services.document_service import expire_documents
            _scheduler.add_job(
                expire_documents,
                trigger=CronTrigger(hour=8, minute=0),
                id="doc_expire_daily",
                name="문서 만료 일일 체크",
                replace_existing=True,
            )
        except Exception as e:
            logger.warning(f"문서 만료 스케줄러 설정 실패: {e}")

        _scheduler.start()
        logger.info("스케줄러 시작 (법령 주간 + 문서 만료 일일)")
    except ImportError:
        logger.warning("apscheduler 미설치 — 법령 자동 동기화 비활성. pip install apscheduler")
    except Exception as e:
        logger.warning(f"스케줄러 시작 실패: {e}")


def _stop_law_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("법령 동기화 스케줄러 종료")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 스케줄러 관리."""
    _start_law_scheduler()
    yield
    _stop_law_scheduler()


app = FastAPI(title="ISMS-P 문서 관리", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# ---------------------------------------------------------------------------
# 라우터 등록
# ---------------------------------------------------------------------------
from app.routes.documents import router as documents_router
from app.routes.mappings import router as mappings_router
from app.routes.gap_analysis import router as gap_router
from app.routes.auditor import router as auditor_router
app.include_router(documents_router)
app.include_router(mappings_router)
app.include_router(gap_router)
app.include_router(auditor_router)

# ---------------------------------------------------------------------------
# 문서 관련 항목 필터 키워드
# ---------------------------------------------------------------------------
DOC_FILTER_SQL = """
    SELECT r.item_code, r.item_title, r.section, r.section_title,
           r.certification_criteria, r.key_checks, r.evidence_examples,
           r.detailed_explanation, r.related_laws, r.defect_cases,
           COALESCE(ec.cnt, 0) AS evidence_count
    FROM isms_requirements r
    LEFT JOIN (
        SELECT item_code, COUNT(*) AS cnt FROM evidences GROUP BY item_code
    ) ec ON r.item_code = ec.item_code
    WHERE r.item_title LIKE '%정책%'
       OR r.item_title LIKE '%문서%'
       OR r.item_title LIKE '%기록%'
       OR r.item_title LIKE '%관리%계획%'
       OR r.item_title LIKE '%보고%'
       OR r.item_title LIKE '%규정%'
       OR r.item_title LIKE '%지침%'
       OR r.certification_criteria LIKE '%문서화%'
       OR r.certification_criteria LIKE '%기록%관리%'
       OR r.certification_criteria LIKE '%정책%수립%'
       OR r.certification_criteria LIKE '%계획%수립%'
       OR r.evidence_examples LIKE '%정책서%'
       OR r.evidence_examples LIKE '%지침서%'
       OR r.evidence_examples LIKE '%절차서%'
       OR r.evidence_examples LIKE '%계획서%'
    ORDER BY r.item_code
"""

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def parse_json(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return [raw] if raw.strip() else []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, search: str = Query(default="")):
    """메인 대시보드 — 문서 관련 항목 목록 + 통계."""
    conn = get_conn()

    if search:
        term = f"%{search}%"
        rows = conn.execute(
            """
            SELECT r.item_code, r.item_title, r.section, r.section_title,
                   r.certification_criteria, r.evidence_examples,
                   COALESCE(ec.cnt, 0) AS evidence_count
            FROM isms_requirements r
            LEFT JOIN (
                SELECT item_code, COUNT(*) AS cnt FROM evidences GROUP BY item_code
            ) ec ON r.item_code = ec.item_code
            WHERE (r.item_title LIKE ? OR r.certification_criteria LIKE ?
                   OR r.evidence_examples LIKE ?)
              AND (r.item_title LIKE '%정책%'
                OR r.item_title LIKE '%문서%'
                OR r.item_title LIKE '%기록%'
                OR r.item_title LIKE '%관리%계획%'
                OR r.item_title LIKE '%보고%'
                OR r.item_title LIKE '%규정%'
                OR r.item_title LIKE '%지침%'
                OR r.certification_criteria LIKE '%문서화%'
                OR r.certification_criteria LIKE '%기록%관리%'
                OR r.certification_criteria LIKE '%정책%수립%'
                OR r.certification_criteria LIKE '%계획%수립%'
                OR r.evidence_examples LIKE '%정책서%'
                OR r.evidence_examples LIKE '%지침서%'
                OR r.evidence_examples LIKE '%절차서%'
                OR r.evidence_examples LIKE '%계획서%')
            ORDER BY r.item_code
            """,
            (term, term, term),
        ).fetchall()
    else:
        rows = conn.execute(DOC_FILTER_SQL).fetchall()

    # 통계
    total = len(rows)
    with_evidence = sum(1 for r in rows if r["evidence_count"] > 0)
    rate = (with_evidence / total * 100) if total else 0

    items = []
    for r in rows:
        examples = parse_json(r["evidence_examples"]) if "evidence_examples" in r.keys() else []
        doc_examples = [
            e for e in examples
            if any(k in e for k in ["정책", "지침", "절차", "계획", "문서", "규정", "보고", "기록", "매뉴얼"])
        ]
        items.append({
            "item_code": r["item_code"],
            "item_title": r["item_title"],
            "section": r["section"],
            "section_title": r["section_title"],
            "criteria": r["certification_criteria"],
            "evidence_count": r["evidence_count"],
            "doc_examples": doc_examples[:5],
        })

    conn.close()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "items": items,
        "total": total,
        "with_evidence": with_evidence,
        "rate": rate,
        "search": search,
    })


@app.get("/item/{item_code}", response_class=HTMLResponse)
async def item_detail(request: Request, item_code: str):
    """항목 상세 페이지."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM isms_requirements WHERE item_code = ?", (item_code,)
    ).fetchone()
    if not row:
        conn.close()
        return HTMLResponse("<h1>항목을 찾을 수 없습니다</h1>", status_code=404)

    evidences = conn.execute(
        "SELECT * FROM evidences WHERE item_code = ? ORDER BY created_at DESC",
        (item_code,),
    ).fetchall()

    # 매핑된 문서 조회 (심사관 뷰)
    try:
        from app.services.mapping_service import get_item_mappings
        mapped_docs = get_item_mappings(item_code)
    except Exception:
        mapped_docs = []

    # 충족유형 조회
    fulfillment_row = conn.execute(
        "SELECT fulfillment_type, confidence FROM item_fulfillment_types WHERE item_code = ?",
        (item_code,),
    ).fetchone()
    fulfillment_type = dict(fulfillment_row) if fulfillment_row else None

    conn.close()

    return templates.TemplateResponse("detail.html", {
        "request": request,
        "r": row,
        "evidences": evidences,
        "key_checks": parse_json(row["key_checks"]),
        "explanations": parse_json(row["detailed_explanation"]),
        "evidence_examples": parse_json(row["evidence_examples"]),
        "related_laws": parse_json(row["related_laws"]),
        "defect_cases": parse_json(row["defect_cases"]),
        "mapped_docs": mapped_docs,
        "fulfillment_type": fulfillment_type,
    })


@app.post("/item/{item_code}/evidence")
async def add_evidence(
    item_code: str,
    evidence_type: str = Form(...),
    content: str = Form(...),
):
    """증적 등록."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO evidences (item_code, evidence_type, content, status) VALUES (?, ?, ?, 'completed')",
        (item_code, evidence_type, content),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(f"/item/{item_code}", status_code=303)


# ---------------------------------------------------------------------------
# 법령 관리 Routes
# ---------------------------------------------------------------------------
@app.get("/laws", response_class=HTMLResponse)
async def law_management(request: Request):
    """법령 최신화 관리 페이지."""
    from app.law_sync import get_law_status_summary, get_sync_logs, ensure_law_tables
    from app.isms_sync import get_isms_sync_status, get_isms_sync_logs

    ensure_law_tables()
    summary = get_law_status_summary()
    logs = get_sync_logs(30)

    # 각 법령별 영향받는 ISMS-P 항목 수 계산
    conn = get_conn()
    for law in summary["laws"]:
        name = law["law_name"]
        short = law.get("law_name_short") or name
        count = conn.execute(
            "SELECT COUNT(*) FROM isms_requirements WHERE related_laws LIKE ? OR related_laws LIKE ?",
            (f"%{name}%", f"%{short}%"),
        ).fetchone()[0]
        law["affected_items"] = count
    conn.close()

    # ISMS-P 인증기준 동기화 현황
    isms_sync = get_isms_sync_status()
    isms_logs = get_isms_sync_logs(10)

    return templates.TemplateResponse("laws.html", {
        "request": request,
        "summary": summary,
        "logs": logs,
        "isms_sync": isms_sync,
        "isms_logs": isms_logs,
    })


@app.post("/laws/sync", response_class=HTMLResponse)
async def trigger_law_sync(request: Request):
    """수동 법령 동기화 트리거."""
    from app.law_sync import sync_all_laws, init_tracked_laws

    init_tracked_laws()
    results = sync_all_laws()

    changed = sum(1 for r in results if r["changed"])
    errors = sum(1 for r in results if r["status"] == "error")

    return RedirectResponse("/laws", status_code=303)


@app.post("/laws/isms-check", response_class=HTMLResponse)
async def trigger_isms_check(request: Request):
    """ISMS-P 인증기준 버전 확인 + 참조 소스 변경 감지."""
    from app.isms_sync import check_kisa_version, detect_changes_from_reference, REFERENCE_SOURCES

    # KISA 공식 버전 확인
    check_kisa_version()

    # 비공식 참조 소스 변경 감지
    for source in REFERENCE_SOURCES:
        detect_changes_from_reference(source["name"])

    return RedirectResponse("/laws", status_code=303)


@app.get("/laws/{law_name}/items", response_class=HTMLResponse)
async def law_affected_items(request: Request, law_name: str):
    """특정 법령 영향받는 항목 목록."""
    from app.law_sync import get_law_affected_items
    import urllib.parse

    decoded_name = urllib.parse.unquote(law_name)
    items = get_law_affected_items(decoded_name)

    return templates.TemplateResponse("law_items.html", {
        "request": request,
        "law_name": decoded_name,
        "items": items,
    })
