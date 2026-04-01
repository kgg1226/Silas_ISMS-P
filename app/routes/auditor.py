"""
심사관 뷰 라우트: 항목별 매핑 문서 역방향 조회 (JSON API)
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.mapping_service import get_item_mappings

router = APIRouter()


@router.get("/item/{item_code}/mappings")
async def item_mappings_json(item_code: str):
    """특정 항목에 매핑된 문서 목록 (JSON)."""
    mappings = get_item_mappings(item_code)
    return JSONResponse(content={"item_code": item_code, "mappings": mappings})
