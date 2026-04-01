"""
ISMS-P 법령 자동 최신화 모듈
법제처 국가법령정보센터 Open API 연동

API 포털: https://open.law.go.kr/LSO/openApi/guideList.do
API 엔드포인트: https://www.law.go.kr/DRF/

환경변수:
  LAW_API_KEY  — 법제처 오픈API OC키 (로그인 이메일 @ 앞부분)
  ISMS_DB_PATH — DB 경로 (기본: data/isms_p.db)

사전 준비:
  1. https://open.law.go.kr 에서 회원가입 + OPEN API 신청
  2. 서버 IP가 등록되어 있어야 호출 가능 (개인 신청 시 자동 등록)
  3. OC키 = 로그인 이메일의 @ 앞부분 (예: user@gmail.com → OC=user)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

logger = logging.getLogger("law_sync")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))

LAW_API_BASE_SEARCH = "https://www.law.go.kr/DRF/lawSearch.do"
LAW_API_BASE_SERVICE = "https://www.law.go.kr/DRF/lawService.do"

# 추적 대상 법령 목록 (DB에 매핑된 법령 기준)
# target: "law"=법률/시행령, "admrul"=행정규칙(고시/지침/훈령)
TRACKED_LAWS = [
    {"name": "개인정보 보호법", "target": "law"},
    {"name": "개인정보의 안전성 확보조치 기준", "target": "admrul"},
    {"name": "정보통신망 이용촉진 및 정보보호 등에 관한 법률", "target": "law"},
    {"name": "전자금융거래법", "target": "law"},
    {"name": "전자상거래 등에서의 소비자보호에 관한 법률", "target": "law"},
    {"name": "전기통신사업법", "target": "law"},
    {"name": "소방시설 설치 및 관리에 관한 법률", "target": "law"},
    {"name": "집적정보통신시설 보호지침", "target": "admrul"},
    {"name": "개인정보 처리 방법에 관한 고시", "target": "admrul"},
    {"name": "개인정보 국외 이전 운영 등에 관한 규정", "target": "admrul"},
    {"name": "신용정보의 이용 및 보호에 관한 법률", "target": "law"},
    {"name": "정보통신기반 보호법", "target": "law"},
]

# 법령명 → DB에서 사용하는 축약명 매핑
LAW_NAME_ALIASES = {
    "정보통신망 이용촉진 및 정보보호 등에 관한 법률": "정보통신망법",
    "전자상거래 등에서의 소비자보호에 관한 법률": "전자상거래법",
    "소방시설 설치 및 관리에 관한 법률": "소방시설법",
    "신용정보의 이용 및 보호에 관한 법률": "신용정보법",
}


# ---------------------------------------------------------------------------
# DB: law_versions 테이블 관리
# ---------------------------------------------------------------------------
LAW_VERSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS law_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    law_name        TEXT NOT NULL,                    -- 법령 정식명칭
    law_name_short  TEXT,                             -- 약칭 (정보통신망법 등)
    law_mst         TEXT,                             -- 법제처 법령ID (MST)
    law_type        TEXT,                             -- 법률/대통령령/부령/고시
    current_version TEXT,                             -- 현행 시행일자 (YYYY-MM-DD)
    amendment_date  TEXT,                             -- 최종 개정일자
    amendment_type  TEXT,                             -- 제개정구분 (일부개정/전부개정/타법개정)
    previous_version TEXT,                            -- 직전 시행일자
    status          TEXT DEFAULT 'active'
                    CHECK (status IN ('active','amended','deprecated','unknown')),
    last_synced     TEXT,                             -- 마지막 동기화 시각
    sync_result     TEXT,                             -- 최종 동기화 결과 메시지
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(law_name)
);

CREATE TABLE IF NOT EXISTS law_sync_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    law_name    TEXT NOT NULL,
    event       TEXT NOT NULL,                        -- sync/amendment_detected/error
    detail      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_law_ver_name   ON law_versions(law_name);
CREATE INDEX IF NOT EXISTS idx_law_ver_status ON law_versions(status);
CREATE INDEX IF NOT EXISTS idx_law_sync_log   ON law_sync_logs(law_name, created_at);
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_law_tables():
    """law_versions, law_sync_logs 테이블이 없으면 생성."""
    with _get_conn() as conn:
        conn.executescript(LAW_VERSIONS_SCHEMA)
    logger.info("law_versions 테이블 준비 완료")


def init_tracked_laws():
    """추적 대상 법령을 law_versions에 초기 등록."""
    ensure_law_tables()
    with _get_conn() as conn:
        for entry in TRACKED_LAWS:
            law_name = entry["name"]
            law_target = entry.get("target", "law")
            short = LAW_NAME_ALIASES.get(law_name, law_name)
            exists = conn.execute(
                "SELECT 1 FROM law_versions WHERE law_name = ?", (law_name,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO law_versions (law_name, law_name_short, law_type, status) VALUES (?, ?, ?, 'unknown')",
                    (law_name, short, law_target),
                )
            else:
                # target 정보 갱신
                conn.execute(
                    "UPDATE law_versions SET law_type = COALESCE(law_type, ?) WHERE law_name = ?",
                    (law_target, law_name),
                )
        conn.commit()
    logger.info(f"추적 대상 법령 {len(TRACKED_LAWS)}건 초기화")


# ---------------------------------------------------------------------------
# 법제처 API 호출
# ---------------------------------------------------------------------------
def _api_key() -> str:
    key = os.getenv("LAW_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "LAW_API_KEY 환경변수를 설정하세요.\n"
            "  OC키 = 로그인 이메일 @ 앞부분 (예: user@gmail.com → user)\n"
            "  API 신청: https://open.law.go.kr/LSO/openApi/guideList.do"
        )
    return key


def _fetch_xml(url: str, params: dict) -> Optional[ET.Element]:
    """법제처 API 호출 후 XML 파싱."""
    params["OC"] = _api_key()
    params["type"] = "XML"
    qs = urllib.parse.urlencode(params)
    full_url = f"{url}?{qs}"

    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "ISMS-P-LawSync/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            return ET.fromstring(data)
    except Exception as e:
        logger.error(f"API 호출 실패: {full_url[:100]}... -> {e}")
        return None


def search_law(law_name: str, target: str = "law") -> Optional[dict]:
    """법령명으로 검색 → 최신 법령 메타정보 반환.
    target: 'law'(법률/시행령) 또는 'admrul'(행정규칙/고시/지침)
    """
    root = _fetch_xml(LAW_API_BASE_SEARCH, {
        "target": target,
        "query": law_name,
        "display": "5",
        "sort": "lasc",
    })
    if root is None:
        return None

    # target에 따라 XML 태그명이 다름
    if target == "admrul":
        return _parse_admrul_search(root, law_name)
    else:
        return _parse_law_search(root, law_name)


def _parse_law_search(root: ET.Element, law_name: str) -> Optional[dict]:
    """법률 검색 결과 파싱."""
    for item in root.iter("law"):
        name_el = item.find("법령명한글")
        if name_el is None:
            name_el = item.find("법령명")
        if name_el is None:
            continue

        item_name = (name_el.text or "").strip()
        if law_name in item_name or item_name in law_name:
            result = {}
            for child in item:
                result[child.tag] = (child.text or "").strip()
            return result

    first = root.find(".//law")
    if first is not None:
        result = {}
        for child in first:
            result[child.tag] = (child.text or "").strip()
        return result

    return None


def _parse_admrul_search(root: ET.Element, law_name: str) -> Optional[dict]:
    """행정규칙 검색 결과 파싱 → 법률 형식으로 정규화."""
    for item in root.iter("admrul"):
        name_el = item.find("행정규칙명")
        if name_el is None:
            continue

        item_name = (name_el.text or "").strip()
        if law_name[:6] in item_name or item_name in law_name:
            # 행정규칙 필드를 법률 형식으로 변환
            raw = {}
            for child in item:
                raw[child.tag] = (child.text or "").strip()

            return {
                "법령명한글": raw.get("행정규칙명", ""),
                "시행일자": raw.get("시행일자", raw.get("발령일자", "")),
                "공포일자": raw.get("발령일자", ""),
                "제개정구분명": raw.get("제개정구분명", ""),
                "법령일련번호": raw.get("행정규칙일련번호", ""),
                "법령ID": raw.get("행정규칙ID", ""),
                "법령구분명": raw.get("행정규칙종류", ""),
                "소관부처명": raw.get("소관부처명", ""),
            }

    # 첫 번째 결과라도 반환
    first = root.find(".//admrul")
    if first is not None:
        raw = {}
        for child in first:
            raw[child.tag] = (child.text or "").strip()
        return {
            "법령명한글": raw.get("행정규칙명", ""),
            "시행일자": raw.get("시행일자", raw.get("발령일자", "")),
            "공포일자": raw.get("발령일자", ""),
            "제개정구분명": raw.get("제개정구분명", ""),
            "법령일련번호": raw.get("행정규칙일련번호", ""),
            "법령ID": raw.get("행정규칙ID", ""),
            "법령구분명": raw.get("행정규칙종류", ""),
            "소관부처명": raw.get("소관부처명", ""),
        }

    return None


def get_law_detail(mst: str) -> Optional[dict]:
    """법령 MST로 상세 조회."""
    root = _fetch_xml(LAW_API_BASE_SERVICE, {
        "target": "law",
        "MST": mst,
    })
    if root is None:
        return None

    result = {}
    # 기본 정보 태그
    for tag in ["법령명_한글", "법령명한글", "시행일자", "공포일자", "제개정구분명",
                 "공포번호", "법령ID", "소관부처명"]:
        el = root.find(f".//{tag}")
        if el is not None:
            result[tag] = (el.text or "").strip()

    # 조문 목록
    articles = []
    for article_el in root.iter("조문단위"):
        a = {}
        for child in article_el:
            a[child.tag] = (child.text or "").strip()
        articles.append(a)
    result["articles"] = articles

    return result


# ---------------------------------------------------------------------------
# 동기화 로직
# ---------------------------------------------------------------------------
def sync_single_law(law_name: str, target: str = "law") -> dict:
    """단일 법령 동기화. 반환: {status, message, changed}."""
    conn = _get_conn()
    ensure_law_tables()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = {"law_name": law_name, "status": "ok", "message": "", "changed": False}

    try:
        # 1. 법제처 검색 (법률 또는 행정규칙)
        search_data = search_law(law_name, target=target)
        # 행정규칙 검색 실패 시 법률로 재시도
        if not search_data and target == "admrul":
            search_data = search_law(law_name, target="law")
        if not search_data:
            result["status"] = "error"
            result["message"] = "법제처 API 검색 결과 없음"
            conn.execute(
                "UPDATE law_versions SET last_synced = ?, sync_result = ? WHERE law_name = ?",
                (now, result["message"], law_name),
            )
            conn.execute(
                "INSERT INTO law_sync_logs (law_name, event, detail) VALUES (?, 'error', ?)",
                (law_name, result["message"]),
            )
            conn.commit()
            return result

        # 2. 시행일자 / 개정일자 추출
        new_effective = search_data.get("시행일자", "")
        amendment_date = search_data.get("공포일자", "")
        amendment_type = search_data.get("제개정구분명", "")
        mst = search_data.get("법령일련번호", search_data.get("법령ID", ""))
        law_type = search_data.get("법령구분명", "")

        # 날짜 형식 정규화 (YYYYMMDD → YYYY-MM-DD)
        def fmt_date(d: str) -> str:
            d = d.strip().replace("-", "")
            if len(d) == 8:
                return f"{d[:4]}-{d[4:6]}-{d[6:]}"
            return d

        new_effective = fmt_date(new_effective)
        amendment_date = fmt_date(amendment_date)

        # 3. DB 현재 상태 비교
        row = conn.execute(
            "SELECT * FROM law_versions WHERE law_name = ?", (law_name,)
        ).fetchone()

        if not row:
            # 신규 등록
            short = LAW_NAME_ALIASES.get(law_name, law_name)
            conn.execute(
                """INSERT INTO law_versions
                   (law_name, law_name_short, law_mst, law_type,
                    current_version, amendment_date, amendment_type,
                    status, last_synced, sync_result)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, '신규 등록')""",
                (law_name, short, mst, law_type,
                 new_effective, amendment_date, amendment_type, now),
            )
            result["message"] = f"신규 등록: 시행일 {new_effective}"
            result["changed"] = True
        else:
            old_version = row["current_version"] or ""

            if new_effective and new_effective != old_version:
                # 개정 감지!
                result["changed"] = True
                new_status = "amended" if amendment_type else "active"
                result["message"] = (
                    f"개정 감지: {old_version} → {new_effective} "
                    f"({amendment_type or '변경'})"
                )

                conn.execute(
                    """UPDATE law_versions SET
                       law_mst = ?, law_type = ?,
                       previous_version = current_version,
                       current_version = ?, amendment_date = ?,
                       amendment_type = ?, status = ?,
                       last_synced = ?, sync_result = ?,
                       updated_at = datetime('now')
                    WHERE law_name = ?""",
                    (mst, law_type, new_effective, amendment_date,
                     amendment_type, new_status, now, result["message"], law_name),
                )

                conn.execute(
                    "INSERT INTO law_sync_logs (law_name, event, detail) VALUES (?, 'amendment_detected', ?)",
                    (law_name, result["message"]),
                )
            else:
                result["message"] = f"변경 없음 (시행일: {new_effective or '확인불가'})"
                conn.execute(
                    "UPDATE law_versions SET last_synced = ?, sync_result = ?, law_mst = ? WHERE law_name = ?",
                    (now, result["message"], mst, law_name),
                )

        conn.execute(
            "INSERT INTO law_sync_logs (law_name, event, detail) VALUES (?, 'sync', ?)",
            (law_name, result["message"]),
        )
        conn.commit()

    except EnvironmentError as e:
        result["status"] = "error"
        result["message"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"동기화 오류: {e}"
        logger.exception(f"법령 동기화 실패: {law_name}")
    finally:
        conn.close()

    return result


def sync_all_laws() -> list[dict]:
    """모든 추적 법령 동기화."""
    init_tracked_laws()
    results = []
    for entry in TRACKED_LAWS:
        law_name = entry["name"]
        target = entry.get("target", "law")
        r = sync_single_law(law_name, target=target)
        results.append(r)
        logger.info(f"[{r['status']}] {law_name}: {r['message']}")
    return results


def update_related_laws_on_amendment(law_name: str) -> int:
    """
    법령 개정 감지 시 isms_requirements.related_laws에서
    해당 법령을 참조하는 항목에 '개정 확인 필요' 플래그 추가.
    """
    conn = _get_conn()
    short = LAW_NAME_ALIASES.get(law_name, law_name)

    # 해당 법령을 참조하는 모든 항목 검색
    rows = conn.execute(
        "SELECT item_code, related_laws FROM isms_requirements WHERE related_laws LIKE ? OR related_laws LIKE ?",
        (f"%{law_name}%", f"%{short}%"),
    ).fetchall()

    updated = 0
    for row in rows:
        # 이미 플래그가 있으면 스킵
        if "개정 확인 필요" in (row["related_laws"] or ""):
            continue
        # 로그만 기록 (자동 변경은 위험하므로 플래그 방식)
        conn.execute(
            "INSERT INTO law_sync_logs (law_name, event, detail) VALUES (?, 'flag_item', ?)",
            (law_name, f"항목 {row['item_code']} 관련 법령 개정 확인 필요"),
        )
        updated += 1

    conn.commit()
    conn.close()
    return updated


# ---------------------------------------------------------------------------
# 상태 조회 (웹 UI / MCP용)
# ---------------------------------------------------------------------------
def get_law_status_summary() -> dict:
    """전체 법령 동기화 상태 요약."""
    conn = _get_conn()
    ensure_law_tables()

    rows = conn.execute(
        "SELECT * FROM law_versions ORDER BY law_name"
    ).fetchall()

    summary = {
        "total": len(rows),
        "active": 0,
        "amended": 0,
        "unknown": 0,
        "deprecated": 0,
        "last_sync": None,
        "laws": [],
    }

    for r in rows:
        status = r["status"] or "unknown"
        summary[status] = summary.get(status, 0) + 1
        if r["last_synced"]:
            if not summary["last_sync"] or r["last_synced"] > summary["last_sync"]:
                summary["last_sync"] = r["last_synced"]
        summary["laws"].append(dict(r))

    conn.close()
    return summary


def get_sync_logs(limit: int = 50) -> list[dict]:
    """최근 동기화 로그."""
    conn = _get_conn()
    ensure_law_tables()
    rows = conn.execute(
        "SELECT * FROM law_sync_logs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_law_affected_items(law_name: str) -> list[dict]:
    """특정 법령이 매핑된 ISMS-P 항목 목록."""
    conn = _get_conn()
    short = LAW_NAME_ALIASES.get(law_name, law_name)
    rows = conn.execute(
        """SELECT item_code, item_title, section, section_title, related_laws
           FROM isms_requirements
           WHERE related_laws LIKE ? OR related_laws LIKE ?
           ORDER BY item_code""",
        (f"%{law_name}%", f"%{short}%"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CLI 실행
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "sync":
        print("법령 동기화 시작...")
        results = sync_all_laws()
        for r in results:
            icon = {"ok": "✅", "error": "❌"}.get(r["status"], "⚠️")
            changed = " [변경감지]" if r["changed"] else ""
            print(f"  {icon} {r['law_name']}: {r['message']}{changed}")
        changed_count = sum(1 for r in results if r["changed"])
        print(f"\n동기화 완료: {len(results)}건 중 {changed_count}건 변경")

    elif cmd == "init":
        init_tracked_laws()
        print("추적 법령 초기화 완료")

    elif cmd == "status":
        summary = get_law_status_summary()
        if not summary["laws"]:
            print("등록된 법령 없음. 'python law_sync.py init' 실행 필요")
        else:
            print(f"추적 법령: {summary['total']}건")
            print(f"  active: {summary['active']}, amended: {summary['amended']}, unknown: {summary['unknown']}")
            print(f"  마지막 동기화: {summary['last_sync'] or '없음'}")
            print()
            for law in summary["laws"]:
                icon = {"active": "✅", "amended": "⚠️", "unknown": "❓", "deprecated": "❌"}.get(law["status"], "?")
                print(f"  {icon} {law['law_name_short'] or law['law_name']}")
                print(f"     시행일: {law['current_version'] or '미확인'} | 동기화: {law['last_synced'] or '없음'}")

    elif cmd == "logs":
        logs = get_sync_logs(30)
        for log in logs:
            print(f"  [{log['created_at']}] {log['event']}: {log['law_name']} - {log['detail']}")

    else:
        print("사용법: python law_sync.py [init|sync|status|logs]")
