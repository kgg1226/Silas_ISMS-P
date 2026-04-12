"""
문서 관리 라우트: 업로드, 목록, 상세, 상태 변경
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Form, UploadFile, File, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.services.document_service import (
    upload_document,
    upload_new_version,
    get_document,
    get_document_list,
    get_document_stats,
    update_document_status,
    get_document_sections,
    get_document_mappings,
    get_document_versions,
)
from app.validators import (
    ValidationError,
    validate_doc_type,
    validate_doc_status,
    validate_file_upload,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

from app.template_helpers import setup_i18n  # noqa: E402
setup_i18n(app=None, templates=templates)


@router.get("/documents", response_class=HTMLResponse)
async def document_list(
    request: Request,
    status: str = Query(default=""),
    doc_type: str = Query(default=""),
    search: str = Query(default=""),
):
    """문서 목록 페이지."""
    docs = get_document_list(status=status, doc_type=doc_type, search=search)
    stats = get_document_stats()

    return templates.TemplateResponse("documents.html", {
        "request": request,
        "documents": docs,
        "stats": stats,
        "filter_status": status,
        "filter_type": doc_type,
        "search": search,
    })


@router.get("/documents/upload", response_class=HTMLResponse)
async def document_upload_form(request: Request):
    """문서 업로드 폼."""
    return templates.TemplateResponse("document_upload.html", {
        "request": request,
        "error": None,
    })


@router.post("/documents/upload")
async def document_upload(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form(...),
    version: str = Form(default="1.0"),
    author: str = Form(default=""),
    approver: str = Form(default=""),
    approval_date: str = Form(default=""),
    effective_date: str = Form(default=""),
    expiry_date: str = Form(default=""),
    description: str = Form(default=""),
):
    """문서 업로드 처리."""
    file_data = await file.read()

    # 입력 검증 (TICKET-003)
    try:
        validate_doc_type(doc_type)
        validate_file_upload(file.filename or "", len(file_data))
    except ValidationError as ve:
        return templates.TemplateResponse("document_upload.html", {
            "request": request,
            "error": ve.message,
        })

    result = upload_document(
        file_data=file_data,
        file_name=file.filename or "unknown",
        title=title,
        doc_type=doc_type,
        version=version,
        author=author,
        approver=approver,
        approval_date=approval_date,
        effective_date=effective_date,
        expiry_date=expiry_date,
        description=description,
    )

    if result["success"]:
        return RedirectResponse(f"/documents/{result['doc_id']}", status_code=303)
    else:
        return templates.TemplateResponse("document_upload.html", {
            "request": request,
            "error": result["error"],
        })


@router.get("/documents/{doc_id}", response_class=HTMLResponse)
async def document_detail(request: Request, doc_id: int):
    """문서 상세 페이지."""
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"문서 #{doc_id}를 찾을 수 없습니다")

    sections = get_document_sections(doc_id)
    mappings = get_document_mappings(doc_id)

    return templates.TemplateResponse("document_detail.html", {
        "request": request,
        "doc": doc,
        "sections": sections,
        "mappings": mappings,
    })


@router.post("/documents/{doc_id}/new-version")
async def document_new_version(
    doc_id: int,
    file: UploadFile = File(...),
    new_version: str = Form(...),
    change_summary: str = Form(default=""),
):
    """문서 새 버전 업로드."""
    file_data = await file.read()
    result = upload_new_version(
        doc_id=doc_id,
        file_data=file_data,
        file_name=file.filename or "unknown",
        new_version=new_version,
        change_summary=change_summary,
    )
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


@router.get("/documents/{doc_id}/versions", response_class=HTMLResponse)
async def document_version_list(request: Request, doc_id: int):
    """문서 버전 이력."""
    doc = get_document(doc_id)
    versions = get_document_versions(doc_id)
    return templates.TemplateResponse("document_detail.html", {
        "request": request,
        "doc": doc,
        "sections": get_document_sections(doc_id),
        "mappings": get_document_mappings(doc_id),
        "versions": versions,
    })


@router.post("/documents/{doc_id}/parse")
async def document_parse(doc_id: int):
    """문서 파싱 트리거."""
    from app.services.parser_service import parse_document_by_id
    parse_document_by_id(doc_id)
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


@router.post("/documents/{doc_id}/status")
async def document_change_status(
    doc_id: int,
    new_status: str = Form(...),
):
    """문서 상태 변경."""
    try:
        validate_doc_status(new_status)
    except ValidationError:
        return RedirectResponse(f"/documents/{doc_id}", status_code=303)
    update_document_status(doc_id, new_status)
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)
