#!/usr/bin/env python3
"""
ISMS-P 증적 자동화를 위한 MCP 서버 (v2 — 실제 DB 스키마 정합)

실제 DB(data/isms_p.db) 스키마 기준:
  - isms_requirements: 20컬럼 (chapter, section, item_code, item_title,
    certification_criteria, key_checks, detailed_explanation,
    evidence_examples, related_laws, defect_cases, notes, ...)
  - evidences: (id, item_code, evidence_type, content, status, created_at)
  - evidence_logs: (id, item_code, evidence_type, content, created_at, created_by)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ---------------------------------------------------------------------------
# 설정 & 로깅
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("isms-p")

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))

# ---------------------------------------------------------------------------
# 서버 인스턴스
# ---------------------------------------------------------------------------
server = Server("isms-p")

# ---------------------------------------------------------------------------
# DB 유틸
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


async def _read(query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    def _work():
        with _connect() as c:
            return c.execute(query, tuple(params)).fetchall()
    return await asyncio.to_thread(_work)


async def _write(query: str, params: Iterable[Any] = ()) -> int:
    def _work():
        with _connect() as c:
            cur = c.execute(query, tuple(params))
            c.commit()
            return cur.lastrowid
    return await asyncio.to_thread(_work)


async def _ensure_tables() -> None:
    """evidences 테이블이 없으면 생성 (isms_requirements는 이미 존재한다고 가정)."""
    rows = await _read(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evidences'"
    )
    if not rows:
        logger.info("Creating 'evidences' table...")
        await _write("""
            CREATE TABLE evidences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'completed',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await _write(
            "CREATE INDEX IF NOT EXISTS idx_evidences_item_code ON evidences(item_code)"
        )


# ---------------------------------------------------------------------------
# 포맷 유틸
# ---------------------------------------------------------------------------

def _err(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=f"❌ {msg}")]


def _ok(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


def _safe(val: Optional[str]) -> str:
    return (val or "").strip()


def _parse_json_list(raw: Optional[str]) -> list[str]:
    """DB에 JSON 배열 문자열로 저장된 필드를 파싱."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return [raw] if raw.strip() else []


# ---------------------------------------------------------------------------
# Tools 정의
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_requirements",
            description="ISMS-P 인증기준 항목을 키워드로 검색합니다. 예: '접근권한', '로그', '암호화'",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "검색 키워드 (예: 접근권한, 로그, 정책)",
                    }
                },
                "required": ["keyword"],
            },
        ),
        Tool(
            name="get_requirement_detail",
            description="특정 ISMS-P 인증기준 항목의 상세 정보를 조회합니다. 예: '1.1.1', '2.10.2'",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {
                        "type": "string",
                        "description": "항목 코드 (예: 1.1.1, 2.10.2)",
                    }
                },
                "required": ["item_code"],
            },
        ),
        Tool(
            name="generate_evidence",
            description="특정 항목에 대한 증적(문서/로그/스크린샷 등)을 저장합니다.",
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
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "점검할 카테고리 (선택사항, 예: '관리체계 기반 마련')",
                    }
                },
            },
        ),
        Tool(
            name="create_audit_report",
            description="기간별 감사 보고서를 생성합니다. (YYYY-MM-DD ~ YYYY-MM-DD)",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "시작 날짜 (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "종료 날짜 (YYYY-MM-DD)"},
                },
            },
        ),
        Tool(
            name="get_evidence_examples",
            description="특정 항목의 증적 예시 목록을 조회합니다. 어떤 증적을 준비해야 하는지 가이드합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {
                        "type": "string",
                        "description": "항목 코드 (예: 1.1.1)",
                    }
                },
                "required": ["item_code"],
            },
        ),
        Tool(
            name="get_defect_cases",
            description="특정 항목의 결함 사례를 조회합니다. 심사 시 주의해야 할 사항을 확인합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {
                        "type": "string",
                        "description": "항목 코드 (예: 1.1.1)",
                    }
                },
                "required": ["item_code"],
            },
        ),
        Tool(
            name="get_related_laws",
            description="특정 항목의 관련 법령을 조회합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {
                        "type": "string",
                        "description": "항목 코드 (예: 1.1.2)",
                    }
                },
                "required": ["item_code"],
            },
        ),
        # --- Phase 8: 문서 매핑 관련 신규 도구 (4개) ---
        Tool(
            name="get_document_mappings",
            description="특정 항목에 매핑된 문서 목록을 조회합니다. 어떤 문서의 몇 번 조항이 이 항목을 충족하는지 확인합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {
                        "type": "string",
                        "description": "항목 코드 (예: 2.1.1)",
                    }
                },
                "required": ["item_code"],
            },
        ),
        Tool(
            name="search_documents",
            description="업로드된 문서를 키워드로 검색합니다. 제목, 유형, 상태로 필터링 가능합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "검색 키워드 (제목, 설명에서 검색)",
                    },
                    "doc_type": {
                        "type": "string",
                        "description": "문서 유형 필터 (정책서, 지침서, 절차서, 계획서, 보고서 등)",
                    },
                    "status": {
                        "type": "string",
                        "description": "상태 필터 (active, expired, draft, archived)",
                    },
                },
            },
        ),
        Tool(
            name="get_gap_analysis",
            description="ISMS-P 전체 101개 항목의 갭 분석 현황을 조회합니다. 충족/부분충족/미충족 현황을 확인합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "chapter": {
                        "type": "string",
                        "description": "장 번호 필터 (1: 관리체계, 2: 보호대책, 3: 개인정보). 미지정 시 전체 조회.",
                    }
                },
            },
        ),
        Tool(
            name="suggest_mappings",
            description="문서 제목/유형 기반으로 매핑할 수 있는 ISMS-P 항목을 추천합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_title": {
                        "type": "string",
                        "description": "문서 제목 (예: '정보보호정책서', '접근권한 관리지침')",
                    },
                    "doc_type": {
                        "type": "string",
                        "description": "문서 유형 (예: '정책서', '지침서')",
                    },
                },
                "required": ["doc_title"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool 라우터
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    try:
        await _ensure_tables()
        args = arguments or {}

        if name == "search_requirements":
            return await _tool_search(_safe(args.get("keyword", "")))

        if name == "get_requirement_detail":
            return await _tool_detail(_safe(args.get("item_code", "")))

        if name == "generate_evidence":
            return await _tool_evidence(
                _safe(args.get("item_code", "")),
                _safe(args.get("evidence_type", "")),
                _safe(args.get("content", "")),
            )

        if name == "check_compliance":
            cat = args.get("category")
            return await _tool_compliance(_safe(cat) if cat else None)

        if name == "create_audit_report":
            return await _tool_report(
                _safe(args.get("start_date")),
                _safe(args.get("end_date")),
            )

        if name == "get_evidence_examples":
            return await _tool_evidence_examples(_safe(args.get("item_code", "")))

        if name == "get_defect_cases":
            return await _tool_defect_cases(_safe(args.get("item_code", "")))

        if name == "get_related_laws":
            return await _tool_related_laws(_safe(args.get("item_code", "")))

        # Phase 8: 문서 매핑 신규 도구
        if name == "get_document_mappings":
            return await _tool_document_mappings(_safe(args.get("item_code", "")))

        if name == "search_documents":
            return await _tool_search_documents(
                _safe(args.get("keyword", "")),
                _safe(args.get("doc_type", "")),
                _safe(args.get("status", "")),
            )

        if name == "get_gap_analysis":
            return await _tool_gap_analysis(_safe(args.get("chapter", "")))

        if name == "suggest_mappings":
            return await _tool_suggest_mappings(
                _safe(args.get("doc_title", "")),
                _safe(args.get("doc_type", "")),
            )

        return _err(f"알 수 없는 도구: {name}")

    except Exception as e:
        logger.exception("Tool error")
        return _err(f"오류 발생 ({name}): {e}")


# ---------------------------------------------------------------------------
# Tool 구현
# ---------------------------------------------------------------------------

async def _tool_search(keyword: str) -> list[TextContent]:
    if not keyword:
        return _err("검색어를 입력해 주세요.")

    term = f"%{keyword}%"
    rows = await _read(
        """
        SELECT item_code, item_title, certification_criteria,
               section, section_title, category
        FROM isms_requirements
        WHERE item_title LIKE ?
           OR certification_criteria LIKE ?
           OR key_checks LIKE ?
           OR detailed_explanation LIKE ?
           OR section_title LIKE ?
           OR category LIKE ?
        ORDER BY item_code
        """,
        (term, term, term, term, term, term),
    )

    if not rows:
        return _ok(f"'{keyword}' 관련 항목을 찾을 수 없습니다.")

    out = StringIO()
    out.write(f"🔍 '{keyword}' 검색 결과: {len(rows)}건\n\n")
    for r in rows:
        out.write(f"**[{r['item_code']}] {r['item_title']}**\n")
        out.write(f"  분류: {r['section']} {r['section_title']}\n")
        criteria = _safe(r["certification_criteria"])
        if len(criteria) > 120:
            criteria = criteria[:120] + "..."
        out.write(f"  인증기준: {criteria}\n\n")
    return _ok(out.getvalue())


async def _tool_detail(item_code: str) -> list[TextContent]:
    if not item_code:
        return _err("항목 코드를 입력해 주세요. (예: 1.1.1)")

    rows = await _read(
        "SELECT * FROM isms_requirements WHERE item_code = ?", (item_code,)
    )
    if not rows:
        return _err(f"항목 코드 '{item_code}'를 찾을 수 없습니다.")
    r = rows[0]

    evidences = await _read(
        """SELECT evidence_type, content, created_at, status
           FROM evidences WHERE item_code = ?
           ORDER BY created_at DESC LIMIT 5""",
        (item_code,),
    )

    out = StringIO()
    out.write("📋 **ISMS-P 인증기준 상세정보**\n\n")
    out.write(f"**항목 코드:** {r['item_code']}\n")
    out.write(f"**장:** {r['chapter']}\n")
    out.write(f"**절:** {r['section']} {r['section_title']}\n")
    out.write(f"**항목명:** {r['item_title']}\n\n")

    out.write(f"**인증기준:**\n{_safe(r['certification_criteria'])}\n\n")

    checks = _parse_json_list(r["key_checks"])
    if checks:
        out.write("**주요 확인사항:**\n")
        for i, c in enumerate(checks, 1):
            out.write(f"  {i}. {c}\n")
        out.write("\n")

    explanations = _parse_json_list(r["detailed_explanation"])
    if explanations:
        out.write("**세부 설명:**\n")
        for item in explanations:
            out.write(f"  - {item}\n")
        out.write("\n")

    laws = _parse_json_list(r["related_laws"])
    if laws:
        out.write("**관련 법령:**\n")
        for law in laws:
            out.write(f"  - {law}\n")
        out.write("\n")

    if evidences:
        out.write(f"**📎 등록된 증적:** {len(evidences)}건 (최근 5개)\n\n")
        for i, e in enumerate(evidences, 1):
            content_preview = _safe(e["content"])[:100]
            out.write(f"  {i}. [{e['evidence_type']}] {content_preview}...\n")
            out.write(f"     상태: {e['status'] or 'completed'} | 생성일: {e['created_at']}\n")
    else:
        out.write("**📎 등록된 증적:** 없음\n")

    return _ok(out.getvalue())


async def _tool_evidence(
    item_code: str, evidence_type: str, content: str
) -> list[TextContent]:
    if not (item_code and evidence_type and content):
        return _err("item_code, evidence_type, content는 필수입니다.")

    exists = await _read(
        "SELECT 1 FROM isms_requirements WHERE item_code = ?", (item_code,)
    )
    if not exists:
        return _err(f"항목 코드 '{item_code}'를 찾을 수 없습니다.")

    eid = await _write(
        "INSERT INTO evidences (item_code, evidence_type, content, status) VALUES (?, ?, ?, 'completed')",
        (item_code, evidence_type, content),
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    preview = content[:200] + "..." if len(content) > 200 else content
    return _ok(
        f"✅ 증적이 등록되었습니다.\n\n"
        f"**증적 ID:** {eid}\n"
        f"**항목:** [{item_code}]\n"
        f"**유형:** {evidence_type}\n"
        f"**내용:** {preview}\n"
        f"**생성일시:** {now}\n"
    )


async def _tool_compliance(category: Optional[str] = None) -> list[TextContent]:
    if category:
        total_rows = await _read(
            "SELECT COUNT(*) AS n FROM isms_requirements WHERE category LIKE ?",
            (f"%{category}%",),
        )
        with_ev_rows = await _read(
            """SELECT COUNT(DISTINCT r.item_code) AS n
               FROM isms_requirements r
               JOIN evidences e ON r.item_code = e.item_code
               WHERE r.category LIKE ?""",
            (f"%{category}%",),
        )
    else:
        total_rows = await _read("SELECT COUNT(*) AS n FROM isms_requirements")
        with_ev_rows = await _read(
            "SELECT COUNT(DISTINCT item_code) AS n FROM evidences"
        )

    total = total_rows[0]["n"]
    with_ev = with_ev_rows[0]["n"]

    by_section = await _read(
        """SELECT r.section, r.section_title,
                  COUNT(DISTINCT r.item_code) AS total,
                  COUNT(DISTINCT e.item_code) AS completed
           FROM isms_requirements r
           LEFT JOIN evidences e ON r.item_code = e.item_code
           GROUP BY r.section, r.section_title
           ORDER BY r.section"""
    )

    rate = (with_ev / total * 100) if total else 0.0
    out = StringIO()
    out.write("📊 **ISMS-P 컴플라이언스 현황**\n\n")
    if category:
        out.write(f"**카테고리 필터:** {category}\n\n")
    out.write(f"**전체 요구사항:** {total}개\n")
    out.write(f"**증적 확보:** {with_ev}개\n")
    out.write(f"**미비:** {total - with_ev}개\n")
    out.write(f"**준수율:** {rate:.1f}%\n\n")

    out.write("**절별 현황:**\n\n")
    for r in by_section:
        sec_rate = (r["completed"] / r["total"] * 100) if r["total"] else 0.0
        if sec_rate >= 80:
            icon = "✅"
        elif sec_rate >= 50:
            icon = "⚠️"
        else:
            icon = "❌"
        out.write(
            f"  {icon} {r['section']} {r['section_title']}: "
            f"{r['completed']}/{r['total']} ({sec_rate:.0f}%)\n"
        )

    return _ok(out.getvalue())


async def _tool_report(
    start_date: Optional[str], end_date: Optional[str]
) -> list[TextContent]:
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = "2020-01-01"

    total_req = (
        await _read("SELECT COUNT(*) AS n FROM isms_requirements")
    )[0]["n"]

    completed = (
        await _read(
            """SELECT COUNT(DISTINCT r.item_code) AS n
               FROM isms_requirements r
               JOIN evidences e ON r.item_code = e.item_code
               WHERE DATE(e.created_at) BETWEEN ? AND ?""",
            (start_date, end_date),
        )
    )[0]["n"]

    total_evidences = (
        await _read(
            "SELECT COUNT(*) AS n FROM evidences WHERE DATE(created_at) BETWEEN ? AND ?",
            (start_date, end_date),
        )
    )[0]["n"]

    by_chapter = await _read(
        """SELECT r.chapter,
                  COUNT(DISTINCT r.item_code) AS total,
                  COUNT(DISTINCT e.item_code) AS done
           FROM isms_requirements r
           LEFT JOIN evidences e
             ON r.item_code = e.item_code
             AND DATE(e.created_at) BETWEEN ? AND ?
           GROUP BY r.chapter
           ORDER BY r.chapter""",
        (start_date, end_date),
    )

    rate = (completed / total_req * 100) if total_req else 0.0

    chapter_names = {
        "1": "관리체계 수립 및 운영",
        "2": "보호대책 요구사항",
        "3": "개인정보 처리 단계별 요구사항",
    }

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
    out.write(f"- 준수율: {rate:.1f}%\n\n")

    out.write("**📁 장별 현황**\n\n")
    for r in by_chapter:
        ch = r["chapter"]
        name = chapter_names.get(ch, f"제{ch}장")
        ch_rate = (r["done"] / r["total"] * 100) if r["total"] else 0.0
        icon = "✅" if ch_rate >= 80 else "⚠️" if ch_rate >= 50 else "❌"
        out.write(f"  {icon} 제{ch}장 {name}: {r['done']}/{r['total']} ({ch_rate:.0f}%)\n")

    out.write("\n" + "=" * 60 + "\n\n")
    out.write("**💡 권장사항**\n\n")
    if total_req and completed < total_req * 0.5:
        out.write("⚠️ 증적 확보율이 50% 미만입니다. 증적 수집을 강화하세요.\n")
    elif total_req and completed < total_req * 0.8:
        out.write("📌 증적 확보율이 양호합니다. 미비 항목 보완이 필요합니다.\n")
    else:
        out.write("✅ 증적 확보율이 우수합니다. 지속 관리가 필요합니다.\n")

    return _ok(out.getvalue())


async def _tool_evidence_examples(item_code: str) -> list[TextContent]:
    if not item_code:
        return _err("항목 코드를 입력해 주세요.")

    rows = await _read(
        "SELECT item_title, evidence_examples FROM isms_requirements WHERE item_code = ?",
        (item_code,),
    )
    if not rows:
        return _err(f"항목 코드 '{item_code}'를 찾을 수 없습니다.")

    r = rows[0]
    examples = _parse_json_list(r["evidence_examples"])

    out = StringIO()
    out.write(f"📎 **[{item_code}] {r['item_title']} — 증적 예시**\n\n")
    if examples:
        for i, ex in enumerate(examples, 1):
            out.write(f"  {i}. {ex}\n")
    else:
        out.write("  등록된 증적 예시가 없습니다.\n")

    return _ok(out.getvalue())


async def _tool_defect_cases(item_code: str) -> list[TextContent]:
    if not item_code:
        return _err("항목 코드를 입력해 주세요.")

    rows = await _read(
        "SELECT item_title, defect_cases FROM isms_requirements WHERE item_code = ?",
        (item_code,),
    )
    if not rows:
        return _err(f"항목 코드 '{item_code}'를 찾을 수 없습니다.")

    r = rows[0]
    cases = _parse_json_list(r["defect_cases"])

    out = StringIO()
    out.write(f"⚠️ **[{item_code}] {r['item_title']} — 결함 사례**\n\n")
    if cases:
        for i, c in enumerate(cases, 1):
            out.write(f"  {i}. {c}\n")
    else:
        out.write("  등록된 결함 사례가 없습니다.\n")

    return _ok(out.getvalue())


async def _tool_related_laws(item_code: str) -> list[TextContent]:
    if not item_code:
        return _err("항목 코드를 입력해 주세요.")

    rows = await _read(
        "SELECT item_title, related_laws FROM isms_requirements WHERE item_code = ?",
        (item_code,),
    )
    if not rows:
        return _err(f"항목 코드 '{item_code}'를 찾을 수 없습니다.")

    r = rows[0]
    laws = _parse_json_list(r["related_laws"])

    out = StringIO()
    out.write(f"⚖️ **[{item_code}] {r['item_title']} — 관련 법령**\n\n")
    if laws:
        for i, law in enumerate(laws, 1):
            out.write(f"  {i}. {law}\n")
    else:
        out.write("  관련 법령 정보가 없습니다.\n")

    return _ok(out.getvalue())


# ---------------------------------------------------------------------------
# Phase 8: 문서 매핑 도구 구현
# ---------------------------------------------------------------------------

async def _tool_document_mappings(item_code: str) -> list[TextContent]:
    """특정 항목에 매핑된 문서 조회 (심사관 뷰)."""
    if not item_code:
        return _err("항목 코드를 입력해 주세요. (예: 2.1.1)")

    # 항목 존재 확인
    item_rows = await _read(
        "SELECT item_title FROM isms_requirements WHERE item_code = ?", (item_code,)
    )
    if not item_rows:
        return _err(f"항목 코드 '{item_code}'를 찾을 수 없습니다.")

    rows = await _read(
        """SELECT m.*, d.title AS doc_title, d.doc_type, d.version AS doc_version,
                  d.status AS doc_status, d.expiry_date,
                  s.section_number, s.section_title AS sec_title,
                  s.page_start, s.page_end
           FROM document_item_mappings m
           JOIN documents d ON m.document_id = d.id
           LEFT JOIN document_sections s ON m.section_id = s.id
           WHERE m.item_code = ?
           ORDER BY m.verified DESC, m.confidence_score DESC""",
        (item_code,),
    )

    out = StringIO()
    out.write(f"📄 **[{item_code}] {item_rows[0]['item_title']} — 매핑된 문서**\n\n")

    if not rows:
        out.write("매핑된 문서가 없습니다. 문서 업로드 후 매핑을 추가해 주세요.\n")
        return _ok(out.getvalue())

    out.write(f"총 {len(rows)}건의 매핑\n\n")

    for i, r in enumerate(rows, 1):
        verified = "✅ 검증됨" if r["verified"] else "⏳ 미검증"
        coverage_icons = {"full": "🟢 전체충족", "partial": "🟡 부분충족", "reference": "⚪ 참조"}
        coverage = coverage_icons.get(r["coverage_level"], r["coverage_level"])
        confidence = int(r["confidence_score"] * 100)

        out.write(f"**{i}. {r['doc_title']}** v{r['doc_version']}\n")

        if r["section_number"]:
            sec_info = f"   → {r['section_number']}"
            if r["sec_title"]:
                sec_info += f" \"{r['sec_title']}\""
            if r["page_start"]:
                sec_info += f" (p.{r['page_start']}"
                if r["page_end"] and r["page_end"] != r["page_start"]:
                    sec_info += f"-{r['page_end']}"
                sec_info += ")"
            out.write(sec_info + "\n")

        out.write(f"   {coverage} | 신뢰도 {confidence}% | {verified}\n")

        # 문서 상태 경고
        if r["doc_status"] == "expired":
            out.write(f"   ⚠️ 문서 만료됨\n")
        elif r["expiry_date"]:
            out.write(f"   📅 만료일: {r['expiry_date']}\n")

        out.write("\n")

    return _ok(out.getvalue())


async def _tool_search_documents(
    keyword: str, doc_type: str, status: str
) -> list[TextContent]:
    """업로드된 문서 검색."""
    query = "SELECT * FROM documents WHERE 1=1"
    params: list = []

    if keyword:
        query += " AND (title LIKE ? OR description LIKE ? OR file_name LIKE ?)"
        term = f"%{keyword}%"
        params.extend([term, term, term])
    if doc_type:
        query += " AND doc_type = ?"
        params.append(doc_type)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT 20"

    rows = await _read(query, params)

    out = StringIO()
    desc_parts = []
    if keyword:
        desc_parts.append(f"키워드='{keyword}'")
    if doc_type:
        desc_parts.append(f"유형={doc_type}")
    if status:
        desc_parts.append(f"상태={status}")
    desc = ", ".join(desc_parts) if desc_parts else "전체"

    out.write(f"🔍 **문서 검색** ({desc}): {len(rows)}건\n\n")

    if not rows:
        out.write("검색 결과가 없습니다.\n")
        return _ok(out.getvalue())

    for i, r in enumerate(rows, 1):
        status_icons = {
            "active": "🟢", "draft": "📝", "expired": "🔴",
            "superseded": "🔄", "archived": "📦",
        }
        icon = status_icons.get(r["status"], "⚪")

        out.write(f"**{i}. {r['title']}** (ID: {r['id']})\n")
        out.write(f"   {icon} {r['status']} | {r['doc_type']} | v{r['version']}\n")
        out.write(f"   파일: {r['file_name']} ({r['file_size'] // 1024}KB)\n")
        if r["author"]:
            out.write(f"   작성자: {r['author']}")
            if r["approver"]:
                out.write(f" | 승인자: {r['approver']}")
            out.write("\n")
        if r["expiry_date"]:
            out.write(f"   만료일: {r['expiry_date']}\n")
        out.write("\n")

    return _ok(out.getvalue())


async def _tool_gap_analysis(chapter: str) -> list[TextContent]:
    """갭 분석 현황 조회."""
    query = """
        SELECT
            r.item_code, r.item_title, r.chapter, r.section, r.section_title,
            COALESCE(ft.fulfillment_type, 'unclassified') AS fulfillment_type,
            COUNT(DISTINCT CASE WHEN m.verified = 1 AND m.coverage_level = 'full' THEN m.id END) AS full_count,
            COUNT(DISTINCT CASE WHEN m.verified = 1 AND m.coverage_level IN ('partial','reference') THEN m.id END) AS partial_count,
            COUNT(DISTINCT CASE WHEN m.verified = 0 THEN m.id END) AS unverified_count,
            COUNT(DISTINCT m.document_id) AS linked_docs
        FROM isms_requirements r
        LEFT JOIN item_fulfillment_types ft ON r.item_code = ft.item_code
        LEFT JOIN document_item_mappings m ON r.item_code = m.item_code
    """
    params: list = []
    if chapter:
        query += " WHERE r.chapter = ?"
        params.append(chapter)
    query += " GROUP BY r.item_code ORDER BY r.item_code"

    rows = await _read(query, params)

    # 통계 집계
    total = len(rows)
    fulfilled = partial = unverified = gap = 0
    gap_items: list[str] = []

    for r in rows:
        if r["full_count"] > 0:
            fulfilled += 1
        elif r["partial_count"] > 0:
            partial += 1
        elif r["unverified_count"] > 0:
            unverified += 1
        else:
            gap += 1
            gap_items.append(f"[{r['item_code']}] {r['item_title']}")

    chapter_names = {
        "1": "관리체계 수립 및 운영",
        "2": "보호대책 요구사항",
        "3": "개인정보 처리 단계별 요구사항",
    }

    out = StringIO()
    scope = f"제{chapter}장 {chapter_names.get(chapter, '')}" if chapter else "전체"
    out.write(f"📊 **ISMS-P 갭 분석** ({scope})\n\n")

    rate = (fulfilled / total * 100) if total else 0.0
    out.write(f"**전체:** {total}개 항목\n")
    out.write(f"🟢 **충족:** {fulfilled}개 ({fulfilled/total*100:.1f}%)\n" if total else "")
    out.write(f"🟡 **부분충족:** {partial}개\n")
    out.write(f"⏳ **미검증:** {unverified}개\n")
    out.write(f"🔴 **미충족:** {gap}개\n\n")

    if fulfilled + partial > 0:
        bar_len = 30
        f_len = int(fulfilled / total * bar_len) if total else 0
        p_len = int(partial / total * bar_len) if total else 0
        g_len = bar_len - f_len - p_len
        out.write(f"[{'█' * f_len}{'▓' * p_len}{'░' * g_len}] {rate:.1f}%\n\n")

    if gap_items and len(gap_items) <= 20:
        out.write("**🔴 미충족 항목:**\n")
        for item in gap_items:
            out.write(f"  - {item}\n")
    elif gap_items:
        out.write(f"**🔴 미충족 항목:** {len(gap_items)}건 (상위 10개)\n")
        for item in gap_items[:10]:
            out.write(f"  - {item}\n")
        out.write(f"  ... 외 {len(gap_items) - 10}건\n")

    return _ok(out.getvalue())


async def _tool_suggest_mappings(doc_title: str, doc_type: str) -> list[TextContent]:
    """문서 제목/유형 기반 항목 추천."""
    if not doc_title:
        return _err("문서 제목을 입력해 주세요.")

    import re as _re

    # 문서 제목에서 토큰 추출
    tokens = set(_re.findall(r"[가-힣a-zA-Z0-9]{2,}", doc_title))
    if doc_type:
        tokens.update(_re.findall(r"[가-힣a-zA-Z0-9]{2,}", doc_type))

    if not tokens:
        return _err("문서 제목에서 키워드를 추출할 수 없습니다.")

    # 전체 항목 로드
    items = await _read(
        """SELECT item_code, item_title, certification_criteria,
                  key_checks, evidence_examples
           FROM isms_requirements ORDER BY item_code"""
    )

    # 매칭 점수 계산
    scored: list[tuple[float, dict]] = []
    for item in items:
        score = 0.0
        # item_title 매칭 (가중치 2.0)
        title_tokens = set(_re.findall(r"[가-힣a-zA-Z0-9]{2,}", item["item_title"] or ""))
        if title_tokens:
            overlap = len(tokens & title_tokens)
            score += (overlap / max(len(title_tokens), 1)) * 2.0

        # certification_criteria 매칭 (가중치 3.0)
        criteria_tokens = set(_re.findall(r"[가-힣a-zA-Z0-9]{2,}", item["certification_criteria"] or ""))
        if criteria_tokens:
            overlap = len(tokens & criteria_tokens)
            score += (overlap / max(len(criteria_tokens), 1)) * 3.0

        # evidence_examples 매칭 (가중치 1.5)
        ee_text = " ".join(_parse_json_list(item["evidence_examples"]))
        ee_tokens = set(_re.findall(r"[가-힣a-zA-Z0-9]{2,}", ee_text))
        if ee_tokens:
            overlap = len(tokens & ee_tokens)
            score += (overlap / max(len(ee_tokens), 1)) * 1.5

        if score > 0.1:
            scored.append((score, dict(item)))

    # 상위 10개
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:10]

    out = StringIO()
    out.write(f"💡 **'{doc_title}' 매핑 추천 항목**\n\n")

    if not top:
        out.write("추천 항목이 없습니다. 좀 더 구체적인 문서 제목을 입력해 보세요.\n")
        return _ok(out.getvalue())

    out.write(f"상위 {len(top)}개 추천:\n\n")
    for i, (score, item) in enumerate(top, 1):
        confidence = min(int(score * 100 / 6.5), 99)  # 최대 점수 6.5 기준 정규화
        criteria = _safe(item["certification_criteria"])
        if len(criteria) > 80:
            criteria = criteria[:80] + "..."
        out.write(f"**{i}. [{item['item_code']}] {item['item_title']}** (관련도 {confidence}%)\n")
        out.write(f"   인증기준: {criteria}\n\n")

    return _ok(out.getvalue())


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main():
    logger.info(f"ISMS-P MCP Server starting (DB: {DB_PATH})")
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
