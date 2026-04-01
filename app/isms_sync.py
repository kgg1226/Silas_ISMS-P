"""
ISMS-P 인증기준 실시간 최신화 모듈

공식 소스 (KISA PDF) 기반 버전 감지 + 비공식 소스 변경 알림

원칙:
  - 공식(KISA PDF + 법제처 API): 실제 데이터 업데이트 대상
  - 비공식(meganad 등): 변경 감지 알림만 (DB 반영 X, 수동 승인 필요)

환경변수:
  ISMS_DB_PATH — DB 경로 (기본: data/isms_p.db)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("isms_sync")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "isms_p.db"
DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", str(DEFAULT_DB))))

# KISA 공지사항 URL (인증기준 안내서 게시 페이지)
KISA_NOTICE_URL = "https://isms.kisa.or.kr/main/csimfo/notice/"
KISA_GUIDE_KEYWORDS = ["인증기준", "안내서", "ISMS-P"]

# 비공식 참조 소스 (변경 감지 전용, DB 반영 X)
REFERENCE_SOURCES = [
    {
        "name": "meganad_github",
        "url": "https://meganad.github.io/ISMS-P/",
        "description": "비공식 ISMS-P 정리 (참고용)",
        "trusted": False,  # 비공식 = 알림만
    },
]

# 현재 DB에 적용된 인증기준 버전
CURRENT_GUIDE_VERSION = "2023.11"
CURRENT_GUIDE_NAME = "ISMS-P 인증기준 안내서 (2023.11)"


# ---------------------------------------------------------------------------
# DB: isms_sync_logs 테이블
# ---------------------------------------------------------------------------
ISMS_SYNC_SCHEMA = """
CREATE TABLE IF NOT EXISTS isms_sync_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code  TEXT,
    field      TEXT,
    event      TEXT NOT NULL,
    source     TEXT,
    detail     TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_isms_sync_event
    ON isms_sync_logs(event, created_at);
CREATE INDEX IF NOT EXISTS idx_isms_sync_item
    ON isms_sync_logs(item_code);
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_isms_sync_tables():
    """isms_sync_logs 테이블이 없으면 생성."""
    with _get_conn() as conn:
        conn.executescript(ISMS_SYNC_SCHEMA)


def _log_event(
    event: str,
    source: str = "",
    item_code: str = "",
    field: str = "",
    detail: str = "",
):
    """동기화 이벤트 로그 기록."""
    ensure_isms_sync_tables()
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO isms_sync_logs (item_code, field, event, source, detail) "
            "VALUES (?, ?, ?, ?, ?)",
            (item_code, field, event, source, detail),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# KISA 공식 PDF 버전 감지
# ---------------------------------------------------------------------------
def check_kisa_version() -> dict:
    """
    KISA 공지사항 페이지에서 인증기준 안내서 최신 버전 확인.
    반환: {
        "current": "2023.11",
        "latest_detected": "2023.11" | "2024.XX" | None,
        "update_available": bool,
        "notice_title": str | None,
        "notice_url": str | None,
        "checked_at": str,
        "error": str | None,
    }
    """
    result = {
        "current": CURRENT_GUIDE_VERSION,
        "latest_detected": None,
        "update_available": False,
        "notice_title": None,
        "notice_url": None,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": None,
    }

    try:
        req = urllib.request.Request(
            KISA_NOTICE_URL,
            headers={"User-Agent": "ISMS-P-Sync/1.0"},
        )
        # SSL 인증서 검증 실패 시 폴백 (로컬 환경용)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                html = resp.read().decode("utf-8", errors="replace")

        # BeautifulSoup 사용 가능하면 정밀 파싱
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            # 공지사항 목록에서 인증기준/안내서 관련 항목 검색
            for link in soup.find_all("a", href=True):
                text = link.get_text(strip=True)
                if any(kw in text for kw in KISA_GUIDE_KEYWORDS):
                    result["notice_title"] = text
                    href = link["href"]
                    if not href.startswith("http"):
                        href = "https://isms.kisa.or.kr" + href
                    result["notice_url"] = href

                    # 연도.월 패턴 추출 (2024.03 등)
                    version_match = re.search(r"20\d{2}[.\-]\d{1,2}", text)
                    if version_match:
                        detected = version_match.group().replace("-", ".")
                        result["latest_detected"] = detected
                        if detected > CURRENT_GUIDE_VERSION:
                            result["update_available"] = True
                    break

        except ImportError:
            # BS4 없으면 정규식 폴백
            pattern = re.compile(
                r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>([^<]*(?:인증기준|안내서|ISMS-P)[^<]*)</a>',
                re.IGNORECASE,
            )
            match = pattern.search(html)
            if match:
                href, text = match.group(1), match.group(2).strip()
                result["notice_title"] = text
                if not href.startswith("http"):
                    href = "https://isms.kisa.or.kr" + href
                result["notice_url"] = href

                version_match = re.search(r"20\d{2}[.\-]\d{1,2}", text)
                if version_match:
                    detected = version_match.group().replace("-", ".")
                    result["latest_detected"] = detected
                    if detected > CURRENT_GUIDE_VERSION:
                        result["update_available"] = True

        if not result["latest_detected"]:
            result["latest_detected"] = CURRENT_GUIDE_VERSION

        _log_event(
            event="version_check",
            source="kisa_pdf",
            detail=json.dumps(
                {
                    "current": result["current"],
                    "detected": result["latest_detected"],
                    "update": result["update_available"],
                },
                ensure_ascii=False,
            ),
        )

    except Exception as e:
        result["error"] = str(e)
        logger.warning(f"KISA 버전 확인 실패: {e}")
        _log_event(
            event="version_check",
            source="kisa_pdf",
            detail=f"오류: {e}",
        )

    return result


# ---------------------------------------------------------------------------
# 비공식 소스 변경 감지 (알림 전용)
# ---------------------------------------------------------------------------
def _fetch_page_hash(url: str) -> Optional[str]:
    """URL의 HTML 콘텐츠 해시 반환."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ISMS-P-Sync/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
        except urllib.error.URLError:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = resp.read()
        return hashlib.sha256(data).hexdigest()
    except Exception as e:
        logger.warning(f"페이지 fetch 실패: {url} -> {e}")
        return None


def detect_changes_from_reference(source_name: str = "meganad_github") -> dict:
    """
    비공식 참조 소스의 변경 감지 (알림 용도만).
    DB 반영은 절대 하지 않음 — KISA PDF 확인 후 수동 승인 필요.

    반환: {
        "source": str,
        "url": str,
        "changed": bool,
        "previous_hash": str | None,
        "current_hash": str | None,
        "checked_at": str,
        "error": str | None,
    }
    """
    source = next(
        (s for s in REFERENCE_SOURCES if s["name"] == source_name),
        None,
    )
    if not source:
        return {"error": f"소스 '{source_name}' 없음", "changed": False}

    result = {
        "source": source_name,
        "url": source["url"],
        "trusted": source.get("trusted", False),
        "changed": False,
        "previous_hash": None,
        "current_hash": None,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": None,
    }

    try:
        ensure_isms_sync_tables()
        conn = _get_conn()

        # 이전 해시 조회
        prev_row = conn.execute(
            """SELECT detail FROM isms_sync_logs
               WHERE source = ? AND event = 'change_check'
               ORDER BY created_at DESC LIMIT 1""",
            (source_name,),
        ).fetchone()

        if prev_row and prev_row["detail"]:
            try:
                prev_data = json.loads(prev_row["detail"])
                result["previous_hash"] = prev_data.get("hash")
            except (json.JSONDecodeError, TypeError):
                pass

        conn.close()

        # 현재 해시 계산
        current_hash = _fetch_page_hash(source["url"])
        result["current_hash"] = current_hash

        if current_hash and result["previous_hash"]:
            if current_hash != result["previous_hash"]:
                result["changed"] = True

        # 로그 기록
        _log_event(
            event="change_check",
            source=source_name,
            detail=json.dumps(
                {
                    "hash": current_hash,
                    "changed": result["changed"],
                    "previous_hash": result["previous_hash"],
                },
                ensure_ascii=False,
            ),
        )

        if result["changed"]:
            _log_event(
                event="change_detected",
                source=source_name,
                detail=(
                    f"비공식 소스 '{source_name}' 변경 감지. "
                    f"KISA 공식 PDF 확인 후 수동 업데이트 필요."
                ),
            )

    except Exception as e:
        result["error"] = str(e)
        logger.warning(f"변경 감지 실패 ({source_name}): {e}")

    return result


# ---------------------------------------------------------------------------
# DB 항목 비교 (수동 업데이트용)
# ---------------------------------------------------------------------------
def compare_item(
    item_code: str,
    field: str,
    new_value: str,
    source: str = "manual",
) -> dict:
    """
    DB의 특정 항목 필드와 새 값을 비교.
    차이가 있으면 로그만 기록 (자동 반영 X).

    반환: {"item_code", "field", "changed", "diff_summary"}
    """
    result = {
        "item_code": item_code,
        "field": field,
        "changed": False,
        "diff_summary": "",
    }

    valid_fields = [
        "certification_criteria", "key_checks", "detailed_explanation",
        "evidence_examples", "related_laws", "defect_cases",
    ]
    if field not in valid_fields:
        result["diff_summary"] = f"유효하지 않은 필드: {field}"
        return result

    conn = _get_conn()
    row = conn.execute(
        f"SELECT {field} FROM isms_requirements WHERE item_code = ?",
        (item_code,),
    ).fetchone()
    conn.close()

    if not row:
        result["diff_summary"] = f"항목 {item_code} 없음"
        return result

    old_value = row[field] or ""

    if old_value.strip() != new_value.strip():
        result["changed"] = True
        old_len = len(old_value)
        new_len = len(new_value)
        result["diff_summary"] = f"변경 감지: {old_len}자 → {new_len}자"

        _log_event(
            event="change_detected",
            source=source,
            item_code=item_code,
            field=field,
            detail=result["diff_summary"],
        )
    else:
        result["diff_summary"] = "동일"

    return result


def apply_item_update(
    item_code: str,
    field: str,
    new_value: str,
    source: str = "manual",
    approved_by: str = "admin",
) -> dict:
    """
    수동 승인 후 항목 필드 업데이트.
    반드시 compare_item()으로 확인 후 호출할 것.
    """
    valid_fields = [
        "certification_criteria", "key_checks", "detailed_explanation",
        "evidence_examples", "related_laws", "defect_cases",
    ]
    if field not in valid_fields:
        return {"success": False, "error": f"유효하지 않은 필드: {field}"}

    conn = _get_conn()

    # 기존 값 백업
    row = conn.execute(
        f"SELECT {field} FROM isms_requirements WHERE item_code = ?",
        (item_code,),
    ).fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": f"항목 {item_code} 없음"}

    old_value = row[field] or ""

    conn.execute(
        f"UPDATE isms_requirements SET {field} = ?, updated_at = datetime('now') WHERE item_code = ?",
        (new_value, item_code),
    )
    conn.commit()
    conn.close()

    _log_event(
        event="manual_update",
        source=source,
        item_code=item_code,
        field=field,
        detail=f"승인자: {approved_by}, 이전 길이: {len(old_value)}자 → {len(new_value)}자",
    )

    return {"success": True, "item_code": item_code, "field": field}


# ---------------------------------------------------------------------------
# 전체 동기화 현황
# ---------------------------------------------------------------------------
def get_isms_sync_status() -> dict:
    """
    ISMS-P 인증기준 동기화 현황 반환.
    """
    ensure_isms_sync_tables()
    conn = _get_conn()

    # 마지막 버전 확인 시각
    last_check = conn.execute(
        """SELECT detail, created_at FROM isms_sync_logs
           WHERE event = 'version_check' AND source = 'kisa_pdf'
           ORDER BY created_at DESC LIMIT 1"""
    ).fetchone()

    # 마지막 변경 감지
    last_change = conn.execute(
        """SELECT source, detail, created_at FROM isms_sync_logs
           WHERE event = 'change_detected'
           ORDER BY created_at DESC LIMIT 1"""
    ).fetchone()

    # 최근 수동 업데이트
    recent_updates = conn.execute(
        """SELECT item_code, field, detail, created_at FROM isms_sync_logs
           WHERE event = 'manual_update'
           ORDER BY created_at DESC LIMIT 5"""
    ).fetchall()

    # 참조 소스 상태
    reference_checks = []
    for source in REFERENCE_SOURCES:
        row = conn.execute(
            """SELECT detail, created_at FROM isms_sync_logs
               WHERE event = 'change_check' AND source = ?
               ORDER BY created_at DESC LIMIT 1""",
            (source["name"],),
        ).fetchone()
        reference_checks.append({
            "name": source["name"],
            "url": source["url"],
            "trusted": source.get("trusted", False),
            "last_checked": row["created_at"] if row else None,
            "last_detail": row["detail"] if row else None,
        })

    conn.close()

    # 버전 확인 결과 파싱
    version_info = {
        "current": CURRENT_GUIDE_VERSION,
        "guide_name": CURRENT_GUIDE_NAME,
        "latest_detected": None,
        "update_available": False,
        "last_checked": None,
    }
    if last_check:
        version_info["last_checked"] = last_check["created_at"]
        try:
            check_data = json.loads(last_check["detail"])
            version_info["latest_detected"] = check_data.get("detected")
            version_info["update_available"] = check_data.get("update", False)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "version": version_info,
        "last_change_detected": {
            "source": last_change["source"] if last_change else None,
            "detail": last_change["detail"] if last_change else None,
            "at": last_change["created_at"] if last_change else None,
        },
        "recent_updates": [dict(r) for r in recent_updates],
        "reference_sources": reference_checks,
    }


def get_isms_sync_logs(limit: int = 30) -> list[dict]:
    """최근 ISMS-P 동기화 로그."""
    ensure_isms_sync_tables()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM isms_sync_logs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )

    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "check":
        print("KISA 인증기준 버전 확인 중...")
        result = check_kisa_version()
        print(f"  현재 버전: {result['current']}")
        print(f"  감지 버전: {result['latest_detected'] or '확인 불가'}")
        print(f"  업데이트: {'있음' if result['update_available'] else '없음'}")
        if result["notice_title"]:
            print(f"  공지: {result['notice_title']}")
        if result["error"]:
            print(f"  오류: {result['error']}")

    elif cmd == "detect":
        print("비공식 소스 변경 감지 중...")
        for source in REFERENCE_SOURCES:
            result = detect_changes_from_reference(source["name"])
            status = "변경 감지" if result["changed"] else "변경 없음"
            print(f"  [{source['name']}] {status}")
            if result["error"]:
                print(f"    오류: {result['error']}")

    elif cmd == "status":
        status = get_isms_sync_status()
        v = status["version"]
        print(f"인증기준: {v['guide_name']}")
        print(f"  현재 버전: {v['current']}")
        print(f"  감지 버전: {v['latest_detected'] or '미확인'}")
        print(f"  업데이트: {'있음' if v['update_available'] else '없음/미확인'}")
        print(f"  마지막 확인: {v['last_checked'] or '없음'}")

        if status["last_change_detected"]["at"]:
            ch = status["last_change_detected"]
            print(f"\n최근 변경 감지:")
            print(f"  소스: {ch['source']}")
            print(f"  시각: {ch['at']}")
            print(f"  상세: {ch['detail']}")

        if status["reference_sources"]:
            print(f"\n참조 소스:")
            for ref in status["reference_sources"]:
                trust = "공식" if ref["trusted"] else "비공식"
                checked = ref["last_checked"] or "미확인"
                print(f"  [{trust}] {ref['name']}: 마지막 확인 {checked}")

    elif cmd == "logs":
        logs = get_isms_sync_logs(20)
        for log in logs:
            print(
                f"  [{log['created_at']}] {log['event']}: "
                f"{log.get('item_code', '')} {log.get('source', '')} — "
                f"{log.get('detail', '')}"
            )

    else:
        print("사용법: python -m app.isms_sync [check|detect|status|logs]")
