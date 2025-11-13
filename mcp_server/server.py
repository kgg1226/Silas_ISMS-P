#!/usr/bin/env python3
"""
ISMS-P 증적 자동화를 위한 MCP 서버 (refactored)
- 기존 Tool 스펙/응답 형식 유지
- DB I/O 정리, 비동기 이벤트루프 블로킹 최소화
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ----- Config -----
DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", str(DEFAULT_DB)))

# ----- MCP Server -----
app = Server("isms-p-server")


# =========================
# DB Utilities & Init
# =========================
@contextmanager
def get_conn():
    """Create a SQLite connection with sane defaults."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    finally:
        conn.close()


def _exec_many(conn: sqlite3.Connection, sql: str, rows: Iterable[Iterable[Any]]) -> None:
    conn.executemany(sql, list(rows))


def _query_all(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()


def _query_one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchone()


def _execute(sql: str, params: Iterable[Any] = ()) -> int:
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.rowcount


def init_database() -> None:
    """ISMS-P 관련 데이터베이스 초기화(테이블 생성 + 샘플 최소 삽입)"""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS isms_requirements (
                item_code   TEXT PRIMARY KEY,
                chapter     TEXT NOT NULL,
                category    TEXT NOT NULL,
                item_title  TEXT NOT NULL,
                description TEXT,
                check_items TEXT,
                related_laws TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code  TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT DEFAULT 'system',
                FOREIGN KEY (item_code) REFERENCES isms_requirements(item_code)
            )
            """
        )

        # 샘플 데이터가 없을 때만 삽입
        cur = conn.execute("SELECT COUNT(*) AS c FROM isms_requirements")
        if cur.fetchone()["c"] == 0:
            sample_data = [
                (
                    "1.1.1",
                    "1. 관리체계 수립 및 운영",
                    "1.1 관리체계 기반 마련",
                    "경영진 참여",
                    "최고경영자는 정보보호 및 개인정보보호 관리체계 수립과 운영에 적극 참여하여야 한다.",
                    "최고경영자의 정보보호 및 개인정보보호 관련 의사결정 참여 여부",
                    "개인정보보호법 제29조",
                ),
                (
                    "1.1.2",
                    "1. 관리체계 수립 및 운영",
                    "1.1 관리체계 기반 마련",
                    "최고책임자 지정",
                    "정보보호 및 개인정보보호 관리체계를 총괄하는 최고책임자를 지정하여야 한다.",
                    "정보보호 및 개인정보보호 최고책임자 지정 여부",
                    "개인정보보호법 제31조",
                ),
                (
                    "2.1.1",
                    "2. 보호대책 요구사항",
                    "2.1 정책, 조직, 자산 관리",
                    "정책의 유지관리",
                    "정보보호 및 개인정보보호 정책을 정기적으로 검토하고 필요시 개정하여야 한다.",
                    "정책 검토 및 개정 이력",
                    "정보통신망법 제45조",
                ),
                (
                    "2.7.1",
                    "2. 보호대책 요구사항",
                    "2.7 암호화 적용",
                    "암호정책 수립 및 적용",
                    "암호 사용에 대한 정책을 수립하고 암호키 관리절차를 포함하여야 한다.",
                    "암호정책 수립 및 적용 여부",
                    "개인정보보호법 제29조",
                ),
            ]
            _exec_many(
                conn,
                """
                INSERT OR IGNORE INTO isms_requirements
                (item_code, chapter, category, item_title, description, check_items, related_laws)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                sample_data,
            )


# =========================
# Domain Functions (sync)
# =========================
def _search_requirements(keyword: str, limit: int = 50) -> list[sqlite3.Row]:
    like = f"%{keyword}%"
    return _query_all(
        """
        SELECT item_code, item_title, description, category
        FROM isms_requirements
        WHERE item_title LIKE ? OR description LIKE ? OR category LIKE ?
        ORDER BY item_code
        LIMIT ?
        """,
        (like, like, like, limit),
    )


def _get_requirement(item_code: str) -> sqlite3.Row | None:
    return _query_one(
        "SELECT * FROM isms_requirements WHERE item_code = ?",
        (item_code,),
    )


def _get_recent_evidences(item_code: str, limit: int = 5) -> list[sqlite3.Row]:
    return _query_all(
        """
        SELECT evidence_type, content, created_at
        FROM evidence_logs
        WHERE item_code = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (item_code, limit),
    )


def _insert_evidence(item_code: str, evidence_type: str, content: str) -> None:
    _execute(
        """
        INSERT INTO evidence_logs (item_code, evidence_type, content)
        VALUES (?, ?, ?)
        """,
        (item_code, evidence_type, content),
    )


def _list_requirements_by_category(category: str | None) -> list[sqlite3.Row]:
    if category:
        return _query_all(
            "SELECT item_code, item_title FROM isms_requirements WHERE category LIKE ?",
            (f"%{category}%",),
        )
    return _query_all("SELECT item_code, item_title FROM isms_requirements")


def _count_evidences(item_code: str) -> int:
    row = _query_one("SELECT COUNT(*) AS c FROM evidence_logs WHERE item_code = ?", (item_code,))
    return int(row["c"] if row else 0)


def _list_evidences_between(start_date: str | None, end_date: str | None) -> list[sqlite3.Row]:
    base = "SELECT item_code, evidence_type, content, created_at FROM evidence_logs"
    if start_date and end_date:
        return _query_all(base + " WHERE created_at BETWEEN ? AND ? ORDER BY created_at DESC", (start_date, end_date))
    return _query_all(base + " ORDER BY created_at DESC")


# =========================
# Formatters
# =========================
def _fmt_search(keyword: str, rows: list[sqlite3.Row]) -> str:
    if not rows:
        return f"'{keyword}' 관련 항목을 찾을 수 없습니다."
    lines = [f"🔍 '{keyword}' 검색 결과 ({len(rows)}건)\n"]
    for r in rows:
        desc = (r["description"] or "").strip()
        desc_preview = (desc[:100] + "...") if len(desc) > 100 else desc
        lines.append(f"📌 [{r['item_code']}] {r['item_title']}\n"
                     f"   카테고리: {r['category']}\n"
                     f"   설명: {desc_preview}\n")
    return "\n".join(lines)


def _fmt_detail(req: sqlite3.Row, evidences: list[sqlite3.Row]) -> str:
    lines = [
        "📋 ISMS-P 인증기준 상세정보\n",
        f"항목코드: {req['item_code']}",
        f"장: {req['chapter']}",
        f"카테고리: {req['category']}",
        f"항목명: {req['item_title']}",
        f"설명: {req['description'] or ''}",
        f"점검항목: {req['check_items'] or ''}",
        f"관련법령: {req['related_laws'] or ''}",
    ]
    if evidences:
        lines.append(f"\n📁 등록된 증적 ({len(evidences)}건):")
        for ev in evidences:
            content = (ev["content"] or "")
            preview = (content[:50] + "...") if len(content) > 50 else content
            lines.append(f"  • [{ev['evidence_type']}] {preview} ({ev['created_at']})")
    else:
        lines.append("\n⚠️ 등록된 증적이 없습니다.")
    return "\n".join(lines)


def _fmt_compliance(reqs: list[sqlite3.Row]) -> str:
    total = len(reqs)
    compliant = 0
    lines = ["📊 컴플라이언스 현황\n"]
    for r in reqs:
        c = _count_evidences(r["item_code"])
        status = "✅" if c > 0 else "❌"
        if c > 0:
            compliant += 1
        lines.append(f"{status} [{r['item_code']}] {r['item_title']} ({c}건)")
    rate = (compliant / total * 100) if total else 0.0
    lines.append(f"\n📈 준수율: {rate:.1f}% ({compliant}/{total})")
    return "\n".join(lines)


def _fmt_report(evidences: list[sqlite3.Row], period: tuple[str, str] | None) -> str:
    lines = ["📑 증적 현황 보고서\n" + "=" * 50 + "\n"]
    if period:
        lines.append(f"기간: {period[0]} ~ {period[1]}\n")
    lines.append(f"총 증적 수: {len(evidences)}건\n")

    # 그룹핑
    by_item: dict[str, list[sqlite3.Row]] = {}
    for ev in evidences:
        by_item.setdefault(ev["item_code"], []).append(ev)

    for item_code, group in by_item.items():
        req = _get_requirement(item_code)
        title = req["item_title"] if req else "알 수 없음"
        lines.append(f"\n[{item_code}] {title}\n  증적 수: {len(group)}건")
        for ev in group[:3]:
            content = ev["content"]
            preview = (content[:40] + "...") if len(content) > 40 else content
            lines.append(f"  • [{ev['evidence_type']}] {preview} ({ev['created_at']})")

    return "\n".join(lines)


# =========================
# MCP: Tools
# =========================
@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_requirements",
            description="ISMS-P 인증기준 항목을 키워드로 검색합니다. 예: '접근권한', '로그', '암호화'",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "검색할 키워드 (예: 접근권한, 로그, 정책)"}
                },
                "required": ["keyword"],
            },
        ),
        Tool(
            name="get_requirement_detail",
            description="특정 ISMS-P 인증기준 항목의 상세 정보를 조회합니다. 예: '1.1.1', '2.3.1'",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {"type": "string", "description": "항목 코드 (예: 1.1.1, 2.3.1)"}
                },
                "required": ["item_code"],
            },
        ),
        Tool(
            name="generate_evidence",
            description="특정 항목에 대한 증적을 자동으로 생성합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {"type": "string", "description": "증적을 생성할 항목 코드"},
                    "evidence_type": {"type": "string", "description": "증적 유형 (문서, 로그, 스크린샷 등)"},
                    "content": {"type": "string", "description": "증적 내용 또는 설명"},
                },
                "required": ["item_code", "evidence_type", "content"],
            },
        ),
        Tool(
            name="check_compliance",
            description="현재 증적 현황을 기반으로 컴플라이언스 준수 여부를 점검합니다.",
            inputSchema={
                "type": "object",
                "properties": {"category": {"type": "string", "description": "점검할 카테고리 (선택사항)"}},
            },
        ),
        Tool(
            name="create_audit_report",
            description="증적 현황 보고서를 생성합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "시작 날짜 (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "종료 날짜 (YYYY-MM-DD)"},
                },
            },
        ),
    ]


# =========================
# MCP: call_tool
# =========================
@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    # DB 작업은 to_thread로 오프로드
    if name == "search_requirements":
        keyword: str = (arguments or {}).get("keyword", "")
        rows = await asyncio.to_thread(_search_requirements, keyword)
        text = _fmt_search(keyword, rows)
        return [TextContent(type="text", text=text)]

    elif name == "get_requirement_detail":
        item_code: str = (arguments or {}).get("item_code", "")
        req = await asyncio.to_thread(_get_requirement, item_code)
        if not req:
            return [TextContent(type="text", text=f"항목 '{item_code}'를 찾을 수 없습니다.")]
        evidences = await asyncio.to_thread(_get_recent_evidences, item_code, 5)
        return [TextContent(type="text", text=_fmt_detail(req, evidences))]

    elif name == "generate_evidence":
        item_code = (arguments or {}).get("item_code", "")
        evidence_type = (arguments or {}).get("evidence_type", "")
        content = (arguments or {}).get("content", "")

        exists = await asyncio.to_thread(_get_requirement, item_code)
        if not exists:
            return [TextContent(type="text", text=f"❌ 항목 '{item_code}'가 존재하지 않습니다.")]
        await asyncio.to_thread(_insert_evidence, item_code, evidence_type, content)
        preview = (content[:100] + "...") if len(content) > 100 else content
        return [TextContent(type="text", text=f"✅ [{item_code}] 증적이 등록되었습니다.\n유형: {evidence_type}\n내용: {preview}")]

    elif name == "check_compliance":
        category = (arguments or {}).get("category")
        reqs = await asyncio.to_thread(_list_requirements_by_category, category)
        text = await asyncio.to_thread(_fmt_compliance, reqs)  # 내부에서 count 쿼리 호출
        return [TextContent(type="text", text=text)]

    elif name == "create_audit_report":
        start_date = (arguments or {}).get("start_date")
        end_date = (arguments or {}).get("end_date")
        evidences = await asyncio.to_thread(_list_evidences_between, start_date, end_date)
        period = (start_date, end_date) if start_date and end_date else None
        return [TextContent(type="text", text=_fmt_report(evidences, period))]

    return [TextContent(type="text", text=f"알 수 없는 도구: {name}")]


# =========================
# Entrypoint
# =========================
async def main():
    init_database()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
