"""
app/i18n.py — Lightweight i18n foundation for ISMS-P web app.

No external dependencies. Translations are plain dicts keyed by locale.
Korean (ko) is the authoritative locale; English (en) and Japanese (ja)
are stubs — missing keys fall back to Korean automatically.

Usage:
    from app.i18n import get_text
    label = get_text("nav.dashboard", locale="ko")  # → "대시보드"
    label = get_text("nav.dashboard", locale="en")  # → "Dashboard"
    label = get_text("nav.dashboard", locale="ja")  # → "ダッシュボード"
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Translation table
# ---------------------------------------------------------------------------
# Rule: every key MUST exist in the "ko" dict.
# "en" and "ja" may omit keys; missing ones fall back to "ko".
# ---------------------------------------------------------------------------

_TRANSLATIONS: dict[str, dict[str, str]] = {
    # -----------------------------------------------------------------------
    # Korean — authoritative / complete
    # -----------------------------------------------------------------------
    "ko": {
        # Navigation
        "nav.brand":        "ISMS-P 문서 관리",
        "nav.dashboard":    "대시보드",
        "nav.documents":    "문서 관리",
        "nav.mappings":     "매핑 관리",
        "nav.gap":          "갭 분석",
        "nav.laws":         "법령 관리",

        # Page titles
        "title.dashboard":  "대시보드 — ISMS-P 문서 관리",
        "title.documents":  "문서 관리",
        "title.mappings":   "매핑 관리",
        "title.gap":        "갭 분석",
        "title.laws":       "법령 관리",

        # Buttons
        "btn.search":       "검색",
        "btn.upload":       "업로드",
        "btn.sync":         "동기화",
        "btn.save":         "저장",
        "btn.cancel":       "취소",
        "btn.delete":       "삭제",
        "btn.detail":       "상세 보기",

        # Status labels
        "status.ok":        "정상",
        "status.warn":      "주의",
        "status.error":     "오류",
        "status.active":    "활성",
        "status.expired":   "만료",
        "status.draft":     "초안",

        # Common labels
        "label.total":      "전체",
        "label.coverage":   "커버리지",
    },

    # -----------------------------------------------------------------------
    # English — stubs (empty strings fall back to Korean)
    # -----------------------------------------------------------------------
    "en": {
        # Navigation
        "nav.brand":        "ISMS-P Document Manager",
        "nav.dashboard":    "Dashboard",
        "nav.documents":    "Documents",
        "nav.mappings":     "Mappings",
        "nav.gap":          "Gap Analysis",
        "nav.laws":         "Laws",

        # Page titles
        "title.dashboard":  "Dashboard — ISMS-P Document Manager",
        "title.documents":  "Document Management",
        "title.mappings":   "Mapping Management",
        "title.gap":        "Gap Analysis",
        "title.laws":       "Law Management",

        # Buttons
        "btn.search":       "Search",
        "btn.upload":       "Upload",
        "btn.sync":         "Sync",
        "btn.save":         "Save",
        "btn.cancel":       "Cancel",
        "btn.delete":       "Delete",
        "btn.detail":       "View Detail",

        # Status labels
        "status.ok":        "OK",
        "status.warn":      "Warning",
        "status.error":     "Error",
        "status.active":    "Active",
        "status.expired":   "Expired",
        "status.draft":     "Draft",

        # Common labels
        "label.total":      "Total",
        "label.coverage":   "Coverage",
    },

    # -----------------------------------------------------------------------
    # Japanese — stubs (empty strings fall back to Korean)
    # -----------------------------------------------------------------------
    "ja": {
        # Navigation
        "nav.brand":        "ISMS-P 文書管理",
        "nav.dashboard":    "ダッシュボード",
        "nav.documents":    "文書管理",
        "nav.mappings":     "マッピング管理",
        "nav.gap":          "ギャップ分析",
        "nav.laws":         "法令管理",

        # Page titles
        "title.dashboard":  "ダッシュボード — ISMS-P 文書管理",
        "title.documents":  "文書管理",
        "title.mappings":   "マッピング管理",
        "title.gap":        "ギャップ分析",
        "title.laws":       "法令管理",

        # Buttons
        "btn.search":       "検索",
        "btn.upload":       "アップロード",
        "btn.sync":         "同期",
        "btn.save":         "保存",
        "btn.cancel":       "キャンセル",
        "btn.delete":       "削除",
        "btn.detail":       "詳細を見る",

        # Status labels
        "status.ok":        "正常",
        "status.warn":      "注意",
        "status.error":     "エラー",
        "status.active":    "有効",
        "status.expired":   "期限切れ",
        "status.draft":     "下書き",

        # Common labels
        "label.total":      "合計",
        "label.coverage":   "カバレッジ",
    },
}

# Supported locales in priority order
SUPPORTED_LOCALES: tuple[str, ...] = ("ko", "en", "ja")
DEFAULT_LOCALE = "ko"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_text(key: str, locale: str = DEFAULT_LOCALE) -> str:
    """Return the translated string for *key* in *locale*.

    Fallback chain:
        1. requested locale
        2. Korean (authoritative)
        3. the key itself (so the UI is never blank)

    Args:
        key:    Dot-separated translation key, e.g. "nav.dashboard".
        locale: BCP-47-style locale code ("ko", "en", "ja").
                Unknown locales fall back to Korean.

    Returns:
        A non-empty string — never raises, never returns an empty string
        when a Korean translation exists.
    """
    # Normalise locale (accept "en-US" → "en", etc.)
    short_locale = locale.split("-")[0].lower() if locale else DEFAULT_LOCALE

    # 1. Try the requested locale
    locale_dict = _TRANSLATIONS.get(short_locale, {})
    value = locale_dict.get(key, "")

    # 2. Fall back to Korean if the value is missing or empty
    if not value and short_locale != DEFAULT_LOCALE:
        value = _TRANSLATIONS[DEFAULT_LOCALE].get(key, "")

    # 3. Final fallback: return the key itself
    return value if value else key
