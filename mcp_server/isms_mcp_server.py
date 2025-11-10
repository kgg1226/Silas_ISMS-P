#!/usr/bin/env python3
"""
ISMS-P 증적 자동화를 위한 MCP 서버
"""

import asyncio
import json
import sqlite3
import os
from datetime import datetime
from typing import Any, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# 환경변수에서 DB 경로 가져오기
DB_PATH = os.getenv('DB_PATH', 'data/isms_p.db')

# MCP 서버 인스턴스
server = Server("isms-p")

def get_db_connection():
    """데이터베이스 연결"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise

@server.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 도구 목록"""
    return [
        Tool(
            name="search_requirements",
            description="ISMS-P 인증기준 항목을 키워드로 검색합니다. 예: '접근권한', '로그', '암호화'",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "검색할 키워드 (예: 접근권한, 로그, 정책)"
                    }
                },
                "required": ["keyword"]
            }
        ),
        Tool(
            name="get_requirement_detail",
            description="특정 ISMS-P 인증기준 항목의 상세 정보를 조회합니다. 예: '1.1.1', '2.3.1'",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {
                        "type": "string",
                        "description": "항목 코드 (예: 1.1.1, 2.3.1)"
                    }
                },
                "required": ["item_code"]
            }
        ),
        Tool(
            name="generate_evidence",
            description="특정 항목에 대한 증적을 자동으로 생성합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {
                        "type": "string",
                        "description": "증적을 생성할 항목 코드"
                    },
                    "evidence_type": {
                        "type": "string",
                        "description": "증적 유형 (문서, 로그, 스크린샷 등)"
                    },
                    "content": {
                        "type": "string",
                        "description": "증적 내용 또는 설명"
                    }
                },
                "required": ["item_code", "evidence_type", "content"]
            }
        ),
        Tool(
            name="check_compliance",
            description="현재 증적 현황을 기반으로 컴플라이언스 준수 여부를 점검합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "점검할 카테고리 (선택사항)"
                    }
                }
            }
        ),
        Tool(
            name="create_audit_report",
            description="증적 현황 보고서를 생성합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "시작 날짜 (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "종료 날짜 (YYYY-MM-DD)"
                    }
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """도구 실행"""
    
    try:
        if name == "search_requirements":
            return await search_requirements(arguments.get("keyword", ""))
        
        elif name == "get_requirement_detail":
            return await get_requirement_detail(arguments.get("item_code", ""))
        
        elif name == "generate_evidence":
            return await generate_evidence(
                arguments.get("item_code", ""),
                arguments.get("evidence_type", ""),
                arguments.get("content", "")
            )
        
        elif name == "check_compliance":
            return await check_compliance(arguments.get("category"))
        
        elif name == "create_audit_report":
            return await create_audit_report(
                arguments.get("start_date"),
                arguments.get("end_date")
            )
        
        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error executing {name}: {str(e)}"
        )]

async def search_requirements(keyword: str) -> list[TextContent]:
    """ISMS-P 요구사항 검색"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 키워드로 검색
    query = """
        SELECT item_code, category, title, description, requirement
        FROM isms_requirements
        WHERE title LIKE ? OR description LIKE ? OR requirement LIKE ? OR category LIKE ?
        ORDER BY item_code
    """
    
    search_term = f"%{keyword}%"
    cursor.execute(query, (search_term, search_term, search_term, search_term))
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        return [TextContent(
            type="text",
            text=f"'{keyword}' 키워드와 관련된 ISMS-P 요구사항을 찾을 수 없습니다."
        )]
    
    # 결과 포맷팅
    output = f"🔍 '{keyword}' 검색 결과: {len(results)}개 항목\n\n"
    
    for row in results:
        output += f"**[{row['item_code']}] {row['title']}**\n"
        output += f"📁 카테고리: {row['category']}\n"
        output += f"📝 설명: {row['description']}\n"
        if row['requirement']:
            output += f"📋 요구사항: {row['requirement']}\n"
        output += "\n" + "-" * 60 + "\n\n"
    
    return [TextContent(type="text", text=output)]

async def get_requirement_detail(item_code: str) -> list[TextContent]:
    """특정 ISMS-P 요구사항 상세 조회"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM isms_requirements WHERE item_code = ?
    """, (item_code,))
    
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return [TextContent(
            type="text",
            text=f"❌ 항목 코드 '{item_code}'를 찾을 수 없습니다."
        )]
    
    # 관련 증적 조회
    cursor.execute("""
        SELECT evidence_type, content, created_at
        FROM evidences
        WHERE item_code = ?
        ORDER BY created_at DESC
    """, (item_code,))
    
    evidences = cursor.fetchall()
    conn.close()
    
    # 결과 포맷팅
    output = f"📋 **ISMS-P 요구사항 상세정보**\n\n"
    output += f"**항목 코드:** {row['item_code']}\n"
    output += f"**카테고리:** {row['category']}\n"
    output += f"**제목:** {row['title']}\n\n"
    output += f"**설명:**\n{row['description']}\n\n"
    
    if row['requirement']:
        output += f"**요구사항:**\n{row['requirement']}\n\n"
    
    if row['control_objective']:
        output += f"**통제목표:**\n{row['control_objective']}\n\n"
    
    # 증적 정보
    if evidences:
        output += f"**📎 증적 현황:** {len(evidences)}건\n\n"
        for i, ev in enumerate(evidences[:5], 1):  # 최근 5개만
            output += f"{i}. [{ev['evidence_type']}] {ev['content'][:100]}...\n"
            output += f"   생성일: {ev['created_at']}\n"
    else:
        output += "**📎 증적 현황:** 등록된 증적이 없습니다.\n"
    
    return [TextContent(type="text", text=output)]

async def generate_evidence(item_code: str, evidence_type: str, content: str) -> list[TextContent]:
    """증적 생성"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 항목 존재 확인
    cursor.execute("SELECT title FROM isms_requirements WHERE item_code = ?", (item_code,))
    req = cursor.fetchone()
    
    if not req:
        conn.close()
        return [TextContent(
            type="text",
            text=f"❌ 항목 코드 '{item_code}'를 찾을 수 없습니다."
        )]
    
    # 증적 저장
    cursor.execute("""
        INSERT INTO evidences (item_code, evidence_type, content, status)
        VALUES (?, ?, ?, 'completed')
    """, (item_code, evidence_type, content))
    
    conn.commit()
    evidence_id = cursor.lastrowid
    conn.close()
    
    output = f"✅ 증적이 성공적으로 생성되었습니다!\n\n"
    output += f"**증적 ID:** {evidence_id}\n"
    output += f"**항목:** [{item_code}] {req['title']}\n"
    output += f"**유형:** {evidence_type}\n"
    output += f"**내용:** {content[:200]}...\n"
    output += f"**생성일시:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return [TextContent(type="text", text=output)]

async def check_compliance(category: Optional[str] = None) -> list[TextContent]:
    """컴플라이언스 점검"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 전체 요구사항 수
    if category:
        cursor.execute("SELECT COUNT(*) FROM isms_requirements WHERE category = ?", (category,))
    else:
        cursor.execute("SELECT COUNT(*) FROM isms_requirements")
    
    total_requirements = cursor.fetchone()[0]
    
    # 증적이 있는 요구사항 수
    if category:
        cursor.execute("""
            SELECT COUNT(DISTINCT r.item_code)
            FROM isms_requirements r
            JOIN evidences e ON r.item_code = e.item_code
            WHERE r.category = ?
        """, (category,))
    else:
        cursor.execute("""
            SELECT COUNT(DISTINCT item_code)
            FROM evidences
        """)
    
    with_evidence = cursor.fetchone()[0]
    
    # 카테고리별 현황
    cursor.execute("""
        SELECT r.category, COUNT(DISTINCT r.item_code) as total,
               COUNT(DISTINCT e.item_code) as completed
        FROM isms_requirements r
        LEFT JOIN evidences e ON r.item_code = e.item_code
        GROUP BY r.category
        ORDER BY r.category
    """)
    
    category_stats = cursor.fetchall()
    conn.close()
    
    # 결과 포맷팅
    compliance_rate = (with_evidence / total_requirements * 100) if total_requirements > 0 else 0
    
    output = f"📊 **ISMS-P 컴플라이언스 현황**\n\n"
    
    if category:
        output += f"**카테고리:** {category}\n\n"
    
    output += f"**전체 요구사항:** {total_requirements}개\n"
    output += f"**증적 확보:** {with_evidence}개\n"
    output += f"**미비:** {total_requirements - with_evidence}개\n"
    output += f"**준수율:** {compliance_rate:.1f}%\n\n"
    
    output += "**📁 카테고리별 현황:**\n\n"
    for cat in category_stats:
        cat_rate = (cat['completed'] / cat['total'] * 100) if cat['total'] > 0 else 0
        status = "✅" if cat_rate >= 80 else "⚠️" if cat_rate >= 50 else "❌"
        output += f"{status} {cat['category']}: {cat['completed']}/{cat['total']} ({cat_rate:.0f}%)\n"
    
    return [TextContent(type="text", text=output)]

async def create_audit_report(start_date: Optional[str] = None, end_date: Optional[str] = None) -> list[TextContent]:
    """감사 보고서 생성"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 기간 설정
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = '2020-01-01'
    
    # 전체 통계
    cursor.execute("SELECT COUNT(*) FROM isms_requirements")
    total_req = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(DISTINCT item_code) FROM evidences
        WHERE DATE(created_at) BETWEEN ? AND ?
    """, (start_date, end_date))
    completed = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM evidences
        WHERE DATE(created_at) BETWEEN ? AND ?
    """, (start_date, end_date))
    total_evidences = cursor.fetchone()[0]
    
    # 카테고리별 통계
    cursor.execute("""
        SELECT r.category, COUNT(DISTINCT e.item_code) as count
        FROM isms_requirements r
        LEFT JOIN evidences e ON r.item_code = e.item_code
        WHERE DATE(e.created_at) BETWEEN ? AND ?
        GROUP BY r.category
    """, (start_date, end_date))
    
    category_report = cursor.fetchall()
    conn.close()
    
    # 보고서 생성
    output = f"📄 **ISMS-P 감사 보고서**\n\n"
    output += f"**기간:** {start_date} ~ {end_date}\n"
    output += f"**생성일시:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    output += "=" * 60 + "\n\n"
    
    output += f"**📊 전체 현황**\n\n"
    output += f"- 전체 요구사항: {total_req}개\n"
    output += f"- 증적 확보 항목: {completed}개\n"
    output += f"- 미비 항목: {total_req - completed}개\n"
    output += f"- 총 증적 수: {total_evidences}건\n"
    output += f"- 준수율: {(completed/total_req*100):.1f}%\n\n"
    
    output += "**📁 카테고리별 현황**\n\n"
    for cat in category_report:
        output += f"- {cat['category']}: {cat['count']}개 항목 완료\n"
    
    output += "\n" + "=" * 60 + "\n\n"
    output += "**💡 권장사항**\n\n"
    
    if completed < total_req * 0.5:
        output += "⚠️ 증적 확보율이 50% 미만입니다. 증적 수집을 강화해야 합니다.\n"
    elif completed < total_req * 0.8:
        output += "📌 증적 확보율이 양호합니다. 미비 항목에 대한 보완이 필요합니다.\n"
    else:
        output += "✅ 증적 확보율이 우수합니다. 지속적인 관리가 필요합니다.\n"
    
    return [TextContent(type="text", text=output)]

async def main():
    """MCP 서버 실행"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())