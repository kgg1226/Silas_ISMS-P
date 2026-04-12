"""
MCP 서버 상태 라우트 — 등록된 도구 목록 및 기본 정보 반환.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

# MCP 서버에 등록된 도구 목록 (mcp_server/isms_mcp_server.py 기준)
MCP_TOOLS = [
    {
        "name": "search_requirements",
        "description": "ISMS-P 인증기준 항목을 키워드로 검색합니다.",
    },
    {
        "name": "get_requirement_detail",
        "description": "특정 ISMS-P 인증기준 항목의 상세 정보를 조회합니다.",
    },
    {
        "name": "generate_evidence",
        "description": "특정 항목에 대한 증적(문서/로그/스크린샷 등)을 저장합니다.",
    },
    {
        "name": "check_compliance",
        "description": "현재 증적 현황을 기반으로 컴플라이언스 준수 여부를 점검합니다.",
    },
    {
        "name": "create_audit_report",
        "description": "기간별 감사 보고서를 생성합니다.",
    },
    {
        "name": "get_evidence_examples",
        "description": "특정 항목의 증적 예시 목록을 조회합니다.",
    },
    {
        "name": "get_defect_cases",
        "description": "특정 항목의 결함 사례를 조회합니다.",
    },
    {
        "name": "get_related_laws",
        "description": "특정 항목의 관련 법령을 조회합니다.",
    },
    {
        "name": "get_document_mappings",
        "description": "특정 항목에 매핑된 문서 목록을 조회합니다.",
    },
    {
        "name": "search_documents",
        "description": "업로드된 문서를 키워드로 검색합니다.",
    },
    {
        "name": "get_gap_analysis",
        "description": "ISMS-P 전체 101개 항목의 갭 분석 현황을 조회합니다.",
    },
    {
        "name": "suggest_mappings",
        "description": "문서 제목/유형 기반으로 매핑할 수 있는 ISMS-P 항목을 추천합니다.",
    },
]

MCP_SERVER_INFO = {
    "name": "isms-p",
    "version": "2.0.0",
    "description": "ISMS-P 증적 자동화 MCP 서버",
    "entry_point": "mcp_server/isms_mcp_server.py",
}


@router.get("/mcp/status")
async def mcp_status():
    """MCP 서버 도구 목록 및 기본 정보를 반환합니다."""
    return JSONResponse({
        "server": MCP_SERVER_INFO,
        "tool_count": len(MCP_TOOLS),
        "tools": MCP_TOOLS,
    })
