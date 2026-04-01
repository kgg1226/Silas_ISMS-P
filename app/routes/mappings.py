"""
매핑 관리 라우트: 수동 생성, 검증, 거부, 목록, 자동 매핑
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.services.mapping_service import (
    create_mapping,
    verify_mapping,
    reject_mapping,
    get_all_mappings,
    get_items_for_mapping,
    auto_map_document,
)
from app.services.document_service import get_document, get_document_sections, get_document_list
from app.services.fulfillment_assessor import assess_mapping, batch_assess_document

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/mappings", response_class=HTMLResponse)
async def mapping_list(
    request: Request,
    item_code: str = Query(default=""),
    document_id: int = Query(default=0),
    verified: str = Query(default=""),
):
    """매핑 목록 페이지."""
    verified_only = verified == "1"
    mappings = get_all_mappings(
        verified_only=verified_only,
        item_code=item_code,
        document_id=document_id,
    )

    return templates.TemplateResponse("mappings.html", {
        "request": request,
        "mappings": mappings,
        "filter_item": item_code,
        "filter_doc_id": document_id,
        "filter_verified": verified,
        "total": len(mappings),
        "verified_count": sum(1 for m in mappings if m["verified"] == 1),
        "unverified_count": sum(1 for m in mappings if m["verified"] == 0),
    })


@router.get("/mappings/create", response_class=HTMLResponse)
async def mapping_create_form(
    request: Request,
    document_id: int = Query(default=0),
    item_code: str = Query(default=""),
):
    """매핑 생성 폼."""
    items = get_items_for_mapping()
    docs = get_document_list(status="active")
    sections = []

    if document_id:
        sections = get_document_sections(document_id)

    return templates.TemplateResponse("mapping_form.html", {
        "request": request,
        "items": items,
        "documents": docs,
        "sections": sections,
        "selected_doc_id": document_id,
        "selected_item_code": item_code,
        "error": None,
    })


@router.post("/mappings/create")
async def mapping_create(
    request: Request,
    document_id: int = Form(...),
    item_code: str = Form(...),
    section_id: int = Form(default=0),
    coverage_level: str = Form(default="partial"),
    notes: str = Form(default=""),
):
    """매핑 저장."""
    result = create_mapping(
        document_id=document_id,
        item_code=item_code,
        section_id=section_id if section_id else None,
        coverage_level=coverage_level,
        notes=notes,
    )

    if result["success"]:
        return RedirectResponse(f"/documents/{document_id}", status_code=303)
    else:
        items = get_items_for_mapping()
        docs = get_document_list(status="active")
        sections = get_document_sections(document_id) if document_id else []

        return templates.TemplateResponse("mapping_form.html", {
            "request": request,
            "items": items,
            "documents": docs,
            "sections": sections,
            "selected_doc_id": document_id,
            "selected_item_code": item_code,
            "error": result["error"],
        })


@router.post("/mappings/{mapping_id}/verify")
async def mapping_verify_route(mapping_id: int):
    """매핑 검증 승인."""
    verify_mapping(mapping_id)
    return RedirectResponse("/mappings", status_code=303)


@router.post("/mappings/{mapping_id}/reject")
async def mapping_reject_route(mapping_id: int):
    """매핑 거부 삭제."""
    reject_mapping(mapping_id)
    return RedirectResponse("/mappings", status_code=303)


@router.post("/documents/{doc_id}/auto-map")
async def document_auto_map(doc_id: int):
    """자동 매핑 트리거 (체크포인트 기반 충족 수준 자동 평가 포함)."""
    auto_map_document(doc_id)
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


@router.post("/mappings/{mapping_id}/reassess")
async def mapping_reassess(mapping_id: int):
    """매핑 충족 수준 재평가."""
    result = assess_mapping(mapping_id)
    if result:
        return RedirectResponse("/mappings", status_code=303)
    return RedirectResponse("/mappings?error=not_found", status_code=303)


@router.post("/documents/{doc_id}/reassess")
async def document_reassess(doc_id: int):
    """문서의 전체 매핑 일괄 재평가."""
    batch_assess_document(doc_id)
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)
