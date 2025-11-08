#!/usr/bin/env python3
"""
ISMS-P 증적 자동화를 위한 MCP 서버
"""

import asyncio
import json
import sqlite3
from datetime import datetime
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

def init_database():
    """ISMS-P 관련 데이터베이스 초기화"""
    conn = sqlite3.connect('isms_p.db')
    cursor = conn.cursor()
    
    # ISMS-P 인증기준 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS isms_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chapter TEXT NOT NULL,
        section TEXT NOT NULL,
        item_code TEXT UNIQUE NOT NULL,
        item_title TEXT NOT NULL,
        certification_criteria TEXT,
        key_checks TEXT,
        detailed_explanation TEXT,
        evidence_examples TEXT,
        defect_cases TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 증적 로그 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS evidence_logs (
        id INTEGER PRIMARY KEY,
        item_code TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

# MCP 서버 생성
app = Server("isms-p-evidence-automation")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 도구 목록 반환"""
    return [
        Tool(
            name="search_requirements",
            description="ISMS-P 인증기준 항목을 검색합니다. 키워드로 관련 항목을 찾을 수 있습니다.",
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
            description="특정 ISMS-P 인증기준 항목의 상세 정보를 조회합니다.",
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

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """도구 실행"""
    
    conn = sqlite3.connect('isms_p.db')
    cursor = conn.cursor()
    
    try:
        if name == "search_requirements":
            keyword = arguments.get("keyword", "")
            cursor.execute('''
                SELECT item_code, item_title, certification_criteria
                FROM isms_requirements
                WHERE item_title LIKE ? OR certification_criteria LIKE ?
            ''', (f'%{keyword}%', f'%{keyword}%'))
            
            results = cursor.fetchall()
            if results:
                output = f"'{keyword}' 검색 결과 ({len(results)}건):\n\n"
                for item in results:
                    output += f"[{item[0]}] {item[1]}\n"
                    output += f"설명: {item[2][:100]}...\n\n"
            else:
                output = f"'{keyword}'에 대한 검색 결과가 없습니다."
            
            return [TextContent(type="text", text=output)]
        
        elif name == "get_requirement_detail":
            item_code = arguments.get("item_code")
            cursor.execute('''
                SELECT * FROM isms_requirements WHERE item_code = ?
            ''', (item_code,))
            
            result = cursor.fetchone()
            if result:
                output = f"=== ISMS-P 인증기준 상세 정보 ===\n\n"
                output += f"항목코드: {result[3]}\n"
                output += f"제목: {result[4]}\n"
                output += f"인증기준: {result[5]}\n"
            else:
                output = f"항목코드 '{item_code}'를 찾을 수 없습니다."
            
            return [TextContent(type="text", text=output)]
        
        elif name == "generate_evidence":
            item_code = arguments.get("item_code")
            evidence_type = arguments.get("evidence_type")
            content = arguments.get("content")
            
            cursor.execute('SELECT item_title FROM isms_requirements WHERE item_code = ?', (item_code,))
            requirement = cursor.fetchone()
            
            if not requirement:
                return [TextContent(type="text", text=f"항목코드 '{item_code}'를 찾을 수 없습니다.")]
            
            cursor.execute('''
                INSERT INTO evidence_logs (item_code, evidence_type, content, created_by)
                VALUES (?, ?, ?, ?)
            ''', (item_code, evidence_type, content, 'system'))
            
            conn.commit()
            
            output = f"증적이 성공적으로 생성되었습니다.\n\n"
            output += f"항목: [{item_code}] {requirement[0]}\n"
            output += f"증적유형: {evidence_type}\n"
            output += f"생성시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            return [TextContent(type="text", text=output)]
        
        elif name == "check_compliance":
            cursor.execute('SELECT item_code, item_title FROM isms_requirements')
            requirements = cursor.fetchall()
            
            output = "=== 컴플라이언스 준수 현황 ===\n\n"
            total = len(requirements)
            compliant = 0
            
            for req in requirements:
                cursor.execute('''
                    SELECT COUNT(*) FROM evidence_logs WHERE item_code = ?
                ''', (req[0],))
                
                evidence_count = cursor.fetchone()[0]
                status = "✓ 준수" if evidence_count > 0 else "✗ 미준수"
                
                if evidence_count > 0:
                    compliant += 1
                
                output += f"{status} [{req[0]}] {req[1]} (증적 {evidence_count}건)\n"
            
            compliance_rate = (compliant / total * 100) if total > 0 else 0
            output += f"\n준수율: {compliant}/{total} ({compliance_rate:.1f}%)"
            
            return [TextContent(type="text", text=output)]
        
        elif name == "create_audit_report":
            start_date = arguments.get("start_date", "2024-01-01")
            end_date = arguments.get("end_date", datetime.now().strftime('%Y-%m-%d'))
            
            cursor.execute('''
                SELECT e.item_code, r.item_title, e.evidence_type, e.created_at
                FROM evidence_logs e
                JOIN isms_requirements r ON e.item_code = r.item_code
                WHERE DATE(e.created_at) BETWEEN ? AND ?
                ORDER BY e.created_at DESC
            ''', (start_date, end_date))
            
            logs = cursor.fetchall()
            
            output = f"=== ISMS-P 증적 현황 보고서 ===\n"
            output += f"기간: {start_date} ~ {end_date}\n\n"
            output += f"총 증적 건수: {len(logs)}건\n\n"
            
            if logs:
                output += "최근 증적 이력:\n"
                for log in logs[:10]:
                    output += f"- [{log[0]}] {log[1]} | {log[2]} | {log[3]}\n"
            else:
                output += "해당 기간 내 증적이 없습니다.\n"
            
            return [TextContent(type="text", text=output)]
        
        else:
            return [TextContent(type="text", text=f"알 수 없는 도구: {name}")]
    
    finally:
        conn.close()

async def main():
    """MCP 서버 시작"""
    init_database()
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main()
