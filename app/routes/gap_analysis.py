"""
갭 분석 대시보드 라우트
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.services.gap_service import get_gap_analysis, export_gap_csv

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/gap", response_class=HTMLResponse)
async def gap_dashboard(
    request: Request,
    chapter: str = Query(default=""),
):
    """갭 분석 대시보드."""
    analysis = get_gap_analysis(chapter_filter=chapter)

    return templates.TemplateResponse("gap_analysis.html", {
        "request": request,
        "summary": analysis["summary"],
        "sections": analysis["sections"],
        "items": analysis["items"],
        "chapter_filter": chapter,
    })


@router.get("/gap/export")
async def gap_export(request: Request):
    """갭 분석 CSV 내보내기."""
    csv_data = export_gap_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=isms_p_gap_analysis.csv"},
    )
