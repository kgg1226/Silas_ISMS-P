#!/usr/bin/env python3
"""
ISMS-P 증적 자동화를 위한 MCP 서버 (리팩터링판)
- 비동기 안전: sqlite3 I/O는 모두 to_thread로 오프로딩
- 스키마 호환: controls/control_sections 기반이면 isms_requirements VIEW를 자동 생성
- 초기화: evidences 테이블 없으면 생성
"""

from __future__ import annotations
import asyncio
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Any, Iterable, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# -----------------------
# 설정 & 로깅
# -----------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("isms-p")

DB_PATH = os.getenv("DB_PATH", "data/isms_p.db")

# -----------------------
# 서버 인스턴스
# -----------------------
server = Server("isms-p")

@dataclass(frozen=True)
class SQL:
    TABLES = """
        SELECT name FROM sqlite_master WHERE type='table';
    """
    HAS_TABLE = "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?;"
    CREATE_EVIDENCES = """
        CREATE TABLE evidences (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          item_code TEXT NOT NULL,
          evidence_type TEXT NOT NULL,
          content TEXT NOT NULL,
          status TEXT DEFAULT 'completed',
          created_at TEXT DEFAULT (datetime('now'))
        );
    """
    INDEX_EVIDENCES = "CREATE INDEX IF NOT EXISTS idx_evidences_item_code ON evidences(item_code);"

    # 네가 만든 DB(controls/control_sections)를 isms_requirements View로 노출
    CREATE_REQ_VIEW = """
        CREATE VIEW isms_requirements AS
        SELECT
          c.control_id AS item_code,
          substr(c.control_id, 1, instr(c.control_id, '.') - 1) AS category,
          c.control_name AS title,
          (
            SELECT cs.text
            FROM control_sections cs
            WHERE cs.control_id = c.control_id
              AND cs.section IN ('세부 설명','주요 확인사항')
            ORDER BY CASE cs.section WHEN '세부 설명' THEN 0 ELSE 1 END
            LIMIT 1
          ) AS description,
          (
            SELECT cs.text
            FROM control_sections cs
            WHERE cs.control_id = c.control_id
              AND cs.section = '인증기준'
            LIMIT 1
          ) AS requirement,
          NULL AS control_objective
        FROM controls c;
    """

# -----------------------
# DB 유틸
# -----------------------
def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

async def run_read(query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    def _work():
        with connect() as c:
            cur = c.execute(query, params)
            return cur.fetchall()
    return await asyncio.to_thread(_work)

async def run_write(query: str, params: Iterable[Any] = ()) -> int:
    def _work():
        with connect() as c:
            cur = c.execute(query, params)
            c.commit()
            return cur.lastrowid
    return await asyncio.to_thread(_work)

async def run_script(script: str) -> None:
    def _work():
        with connect() as c:
            c.executescript(script)
            c.commit()
    await asyncio.to_thread(_work)

async def table_exists(name: str) -> bool:
    rows = await run_read(SQL.HAS_TABLE, (name,))
    return bool(rows)

async def ensure_schema() -> None:
    """실행 시 스키마 호환/초기화: evidences 없으면 생성, isms_requirements 없으면 VIEW 생성."""
    # evidences
    if not await table_exists("evidences"):
        logger.info("Creating 'evidences' table...")
        await run_script(SQL.CREATE_EVIDENCES)
        await run_write(SQL.INDEX_EVIDENCES)

    # requirements
    has_isms_req = await table_exists("isms_requirements")
    if not has_isms_req:
        # controls/control_sections 기반이면 View 생성
        if await table_exists("controls") and await table_exists("control_sections"):
            logger.info("Creating 'isms_requirements' VIEW from controls/control_sections...")
            await run_script(SQL.CREATE_REQ_VIEW)
        else:
            # 진짜 테이블이 있다고 가정하는 경우는 그냥 넘어감(외부에서 제공)
            logger.warning(
                "No 'isms_requirements' and no (controls/control_sections). "
                "Provide your own 'isms_requirements' table if needed."
            )

# -----------------------
# 포맷 유틸
# -----------------------
def fmt_error(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=f"❌ {msg}")]

def fmt_text(lines: Iterable[str]) -> list[TextContent]:
    return [TextContent(type="text", text="".join(lines))]

def safe_strip(s: Optional[str]) -> str:
    return (s or "").strip()

# -----------------------
# Tools 정의
# -----------------------
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_requirements",
            description="ISMS-P 인증기준 항목을 키워드로 검색합니다. 예: '접근권한', '로그', '암호화'",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "검색 키워드"}
                },
                "required": ["keyword"]
            }
        ),
        Tool(
            name="get_requirement_detail",
            description="특정 ISMS-P 인증기준 항목의 상세 정보를 조회합니다. 예: '2.10.2'",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {"type": "string", "description": "항목 코드 (예: 2.10.2)"}
                },
                "required": ["item_code"]
            }
        ),
        Tool(
            name="generate_evidence",
            description="특정 항목에 대한 증적(문서/로그/스크린샷 등)을 저장합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {"type": "string"},
                    "evidence_type": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["item_code", "evidence_type", "content"]
            }
        ),
        Tool(
            name="check_compliance",
            description="증적 현황 기반으로 준수율을 집계합니다. category를 주면 해당 영역만 계산.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string"}
                }
            }
        ),
        Tool(
            name="create_audit_report",
            description="기간별 감사 보고서를 생성합니다. (YYYY-MM-DD ~ YYYY-MM-DD)",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                }
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    try:
        # 스키마 보장
        await ensure_schema()

        if name == "search_requirements":
            return await tool_search_requirements(safe_strip(arguments.get("keyword", "")))

        if name == "get_requirement_detail":
            return await tool_get_requirement_detail(safe_strip(arguments.get("item_code", "")))

        if name == "generate_evidence":
            return await tool_generate_evidence(
                safe_strip(arguments.get("item_code", "")),
                safe_strip(arguments.get("evidence_type", "")),
                safe_strip(arguments.get("content", "")),
            )

        if name == "check_compliance":
            cat = arguments.get("category")
            return await tool_check_compliance(safe_strip(cat) if cat else None)

        if name == "create_audit_report":
            return await tool_create_audit_report(
                safe_strip(arguments.get("start_date")),
                safe_strip(arguments.get("end_date")),
            )

        return fmt_error(f"Unknown tool: {name}")

    except Exception as e:
        logger.exception("Tool error")
        return fmt_error(f"Error executing {name}: {e}")

# -----------------------
# Tool 구현
# -----------------------
async def tool_search_requirements(keyword: str) -> list[TextContent]:
    if not keyword:
        return fmt_error("검색어를 입력해 주세요.")

    q = """
        SELECT item_code, category, title, COALESCE(description,'') AS description,
               COALESCE(requirement,'') AS requirement
        FROM isms_requirements
        WHERE title LIKE ? OR description LIKE ? OR requirement LIKE ? OR category LIKE ?
        ORDER BY item_code;
    """
    term = f"%{keyword}%"
    rows = await run_read(q, (term, term, term, term))
    if not rows:
        return fmt_text([f"🔍 '{keyword}' 로 검색된 항목이 없습니다.\n"])

    out = StringIO()
    out.write(f"🔍 '{keyword}' 검색 결과: {len(rows)}개 항목\n\n")
    for r in rows:
        out.write(f"**[{r['item_code']}] {r['title']}**\n")
        if r["category"]:
            out.write(f"📁 카테고리: {r['category']}\n")
        if r["description"]:
            out.write(f"📝 설명: {r['description']}\n")
        if r["requirement"]:
            out.write(f"📋 요구사항: {r['requirement']}\n")
        out.write("\n" + "-" * 60 + "\n\n")
    return fmt_text([out.getvalue()])

async def tool_get_requirement_detail(item_code: str) -> list[TextContent]:
    if not item_code:
        return fmt_error("항목 코드를 입력해 주세요. (예: 2.10.2)")

    row = (await run_read("SELECT * FROM isms_requirements WHERE item_code = ?;", (item_code, )))
    if not row:
        return fmt_error(f"항목 코드 '{item_code}'를 찾을 수 없습니다.")
    r = row[0]

    ev = await run_read(
        "SELECT evidence_type, content, created_at FROM evidences WHERE item_code = ? ORDER BY created_at DESC LIMIT 5;",
        (item_code,))
    out = StringIO()
    out.write("📋 **ISMS-P 요구사항 상세정보**\n\n")
    out.write(f"**항목 코드:** {r['item_code']}\n")
    if r["category"]:
        out.write(f"**카테고리:** {r['category']}\n")
    out.write(f"**제목:** {r['title']}\n\n")
    if r["description"]:
        out.write("**설명:**\n" + r["description"] + "\n\n")
    if r["requirement"]:
        out.write("**요구사항:**\n" + r["requirement"] + "\n\n")
    # sqlite3.Row는 .get()을 지원하지 않으므로 키 존재 여부 확인
    if "control_objective" in r.keys() and r["control_objective"]:
        out.write("**통제목표:**\n" + str(r["control_objective"]) + "\n\n")

    if ev:
        out.write(f"**📎 증적 현황:** {len(ev)}건 (최근 5개)\n\n")
        for i, e in enumerate(ev, 1):
            out.write(f"{i}. [{e['evidence_type']}] { (e['content'] or '')[:100] }...\n")
            out.write(f"   생성일: {e['created_at']}\n")
    else:
        out.write("**📎 증적 현황:** 등록된 증적이 없습니다.\n")

    return fmt_text([out.getvalue()])

async def tool_generate_evidence(item_code: str, evidence_type: str, content: str) -> list[TextContent]:
    if not (item_code and evidence_type and content):
        return fmt_error("item_code, evidence_type, content는 필수입니다.")

    # 항목 존재 확인
    exists = await run_read("SELECT 1 FROM isms_requirements WHERE item_code = ?;", (item_code,))
    if not exists:
        return fmt_error(f"항목 코드 '{item_code}'를 찾을 수 없습니다.")

    eid = await run_write(
        "INSERT INTO evidences (item_code, evidence_type, content, status) VALUES (?, ?, ?, 'completed');",
        (item_code, evidence_type, content)
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = (
        "✅ 증적이 성공적으로 생성되었습니다!\n\n"
        f"**증적 ID:** {eid}\n"
        f"**항목:** [{item_code}]\n"
        f"**유형:** {evidence_type}\n"
        f"**내용:** {content[:200]}...\n"
        f"**생성일시:** {now}\n"
    )
    return fmt_text([out])

async def tool_check_compliance(category: Optional[str] = None) -> list[TextContent]:
    if category:
        total = (await run_read("SELECT COUNT(*) AS n FROM isms_requirements WHERE category = ?;", (category,)))[0]["n"]
        with_ev = (await run_read("""
            SELECT COUNT(DISTINCT r.item_code) AS n
            FROM isms_requirements r
            JOIN evidences e ON r.item_code = e.item_code
            WHERE r.category = ?;""", (category,)))[0]["n"]
    else:
        total = (await run_read("SELECT COUNT(*) AS n FROM isms_requirements;"))[0]["n"]
        with_ev = (await run_read("SELECT COUNT(DISTINCT item_code) AS n FROM evidences;"))[0]["n"]

    by_cat = await run_read("""
        SELECT r.category AS category,
               COUNT(DISTINCT r.item_code) AS total,
               COUNT(DISTINCT e.item_code) AS completed
        FROM isms_requirements r
        LEFT JOIN evidences e ON r.item_code = e.item_code
        GROUP BY r.category
        ORDER BY r.category;
    """)

    rate = (with_ev / total * 100) if total else 0.0
    out = StringIO()
    out.write("📊 **ISMS-P 컴플라이언스 현황**\n\n")
    if category: out.write(f"**카테고리:** {category}\n\n")
    out.write(f"**전체 요구사항:** {total}개\n")
    out.write(f"**증적 확보:** {with_ev}개\n")
    out.write(f"**미비:** {total - with_ev}개\n")
    out.write(f"**준수율:** {rate:.1f}%\n\n")
    out.write("**📁 카테고리별 현황:**\n\n")
    for r in by_cat:
        cat_rate = (r["completed"] / r["total"] * 100) if r["total"] else 0.0
        status = "✅" if cat_rate >= 80 else "⚠️" if cat_rate >= 50 else "❌"
        out.write(f"{status} {r['category']}: {r['completed']}/{r['total']} ({cat_rate:.0f}%)\n")
    return fmt_text([out.getvalue()])

async def tool_create_audit_report(start_date: Optional[str], end_date: Optional[str]) -> list[TextContent]:
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = "2020-01-01"

    total_req = (await run_read("SELECT COUNT(*) AS n FROM isms_requirements;"))[0]["n"]
    completed = (await run_read("""
        SELECT COUNT(DISTINCT r.item_code) AS n
        FROM isms_requirements r
        JOIN evidences e ON r.item_code = e.item_code
        WHERE DATE(e.created_at) BETWEEN ? AND ?;
    """, (start_date, end_date)))[0]["n"]
    total_evidences = (await run_read("""
        SELECT COUNT(*) AS n FROM evidences
        WHERE DATE(created_at) BETWEEN ? AND ?;
    """, (start_date, end_date)))[0]["n"]
    by_cat = await run_read("""
        SELECT r.category, COUNT(DISTINCT e.item_code) AS cnt
        FROM isms_requirements r
        LEFT JOIN evidences e ON r.item_code = e.item_code
        WHERE DATE(e.created_at) BETWEEN ? AND ?
        GROUP BY r.category;
    """, (start_date, end_date))

    out = StringIO()
    out.write("📄 **ISMS-P 감사 보고서**\n\n")
    out.write(f"**기간:** {start_date} ~ {end_date}\n")
    out.write(f"**생성일시:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    out.write("=" * 60 + "\n\n")
    out.write("**📊 전체 현황**\n\n")
    out.write(f"- 전체 요구사항: {total_req}개\n")
    out.write(f"- 증적 확보 항목: {completed}개\n")
    out.write(f"- 미비 항목: {total_req - completed}개\n")
    out.write(f"- 총 증적 수: {total_evidences}건\n")
    out.write(f"- 준수율: {(completed/total_req*100):.1f}%\n\n" if total_req else "- 준수율: 0.0%\n\n")
    out.write("**📁 카테고리별 현황**\n\n")
    for r in by_cat:
        out.write(f"- {r['category']}: {r['cnt']}개 항목 완료\n")
    out.write("\n" + "=" * 60 + "\n\n")
    out.write("**💡 권장사항**\n\n")
    if total_req and completed < total_req * 0.5:
        out.write("⚠️ 증적 확보율이 50% 미만입니다. 증적 수집을 강화하세요.\n")
    elif total_req and completed < total_req * 0.8:
        out.write("📌 증적 확보율이 양호합니다. 미비 항목 보완이 필요합니다.\n")
    else:
        out.write("✅ 증적 확보율이 우수합니다. 지속 관리가 필요합니다.\n")
    return fmt_text([out.getvalue()])

# -----------------------
# 메인
# -----------------------
async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
