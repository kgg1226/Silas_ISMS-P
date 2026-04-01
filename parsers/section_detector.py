"""
한국어 법률/정책 문서 조항 패턴 감지기

문서 텍스트에서 제1장, 제1조, 1.1.1절 등의 구조를 감지하여
계층적 섹션 트리를 생성한다.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawSection:
    """파서에서 반환하는 원시 섹션."""
    text: str
    page_number: int = 0


@dataclass
class Section:
    """감지된 섹션 노드."""
    section_number: str       # "제1조", "1.2.3", "제2장" 등
    section_title: str = ""
    content: str = ""
    page_start: int = 0
    page_end: int = 0
    depth: int = 0            # 0=최상위, 1=하위, 2=하하위...
    sort_order: int = 0
    section_type: str = ""    # chapter, section, article, clause, numbered
    children: list["Section"] = field(default_factory=list)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()


# ---------------------------------------------------------------------------
# 조항 패턴 (우선순위 순서)
# ---------------------------------------------------------------------------
# 각 패턴: (regex, type, depth)
SECTION_PATTERNS: list[tuple[re.Pattern, str, int]] = [
    # 제N장 (최상위)
    (re.compile(r"^제\s*(\d+)\s*장\s+(.+)$", re.MULTILINE), "chapter", 0),
    # 제N절
    (re.compile(r"^제\s*(\d+)\s*절\s+(.+)$", re.MULTILINE), "section", 1),
    # 제N조 (제목 포함)
    (re.compile(r"^제\s*(\d+)\s*조\s*[（(]\s*(.+?)\s*[)）]\s*$", re.MULTILINE), "article", 2),
    # 제N조 (제목 없음)
    (re.compile(r"^제\s*(\d+)\s*조\s+(.+)$", re.MULTILINE), "article", 2),
    # 제N항
    (re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩]\s*(.+)$", re.MULTILINE), "clause", 3),
    # 숫자 제목: 1. 또는 1.1 또는 1.1.1
    (re.compile(r"^(\d+(?:\.\d+)+)\s*[.)]?\s+(.+)$", re.MULTILINE), "numbered", 1),
    (re.compile(r"^(\d+)\s*[.)]\s+(.+)$", re.MULTILINE), "numbered_top", 0),
]

# 원문자 → 숫자 매핑
CIRCLED_NUMS = {
    "①": 1, "②": 2, "③": 3, "④": 4, "⑤": 5,
    "⑥": 6, "⑦": 7, "⑧": 8, "⑨": 9, "⑩": 10,
}


def _normalize(text: str) -> str:
    """유니코드 NFC 정규화."""
    return unicodedata.normalize("NFC", text)


def detect_sections(raw_sections: list[RawSection]) -> list[Section]:
    """
    원시 텍스트 블록들에서 조항 구조를 감지.

    Args:
        raw_sections: 페이지별 텍스트 블록 목록

    Returns:
        계층적 Section 트리 (최상위 리스트)
    """
    # 1. 전체 텍스트를 줄 단위로 분석
    detected: list[Section] = []
    all_lines: list[tuple[str, int]] = []  # (line, page_number)

    for raw in raw_sections:
        text = _normalize(raw.text)
        for line in text.split("\n"):
            line = line.strip()
            if line:
                all_lines.append((line, raw.page_number))

    # 2. 각 줄에서 패턴 매칭
    current_section: Optional[Section] = None
    sort_counter = 0

    for line, page in all_lines:
        matched = False

        for pattern, sec_type, depth in SECTION_PATTERNS:
            m = pattern.match(line)
            if m:
                # 새 섹션 시작
                if current_section and not current_section.content.strip():
                    # 빈 섹션이면 제목만 있는 것 — 유지
                    pass

                groups = m.groups()

                if sec_type == "clause":
                    # 원문자 항
                    circled = line[0]
                    num = CIRCLED_NUMS.get(circled, 0)
                    sec_number = f"제{num}항"
                    sec_title = groups[0].strip() if groups else ""
                else:
                    sec_number_raw = groups[0] if groups else ""
                    sec_title = groups[1].strip() if len(groups) > 1 else ""

                    if sec_type == "chapter":
                        sec_number = f"제{sec_number_raw}장"
                    elif sec_type == "section":
                        sec_number = f"제{sec_number_raw}절"
                    elif sec_type == "article":
                        sec_number = f"제{sec_number_raw}조"
                    elif sec_type in ("numbered", "numbered_top"):
                        sec_number = sec_number_raw
                    else:
                        sec_number = sec_number_raw

                sort_counter += 1
                current_section = Section(
                    section_number=sec_number,
                    section_title=sec_title,
                    content="",
                    page_start=page,
                    page_end=page,
                    depth=depth,
                    sort_order=sort_counter,
                    section_type=sec_type,
                )
                detected.append(current_section)
                matched = True
                break

        if not matched and current_section:
            # 현재 섹션의 본문에 추가
            if current_section.content:
                current_section.content += "\n"
            current_section.content += line
            current_section.page_end = page

    # 3. 내용이 없는 섹션 정리 (제목만 있는 장/절은 유지)
    result = [s for s in detected if s.content.strip() or s.section_type in ("chapter", "section")]

    # 4. 섹션이 하나도 감지되지 않으면 전체를 하나의 섹션으로
    if not result and all_lines:
        full_text = "\n".join(line for line, _ in all_lines)
        result = [Section(
            section_number="전체",
            section_title="문서 전체",
            content=full_text,
            page_start=all_lines[0][1] if all_lines else 0,
            page_end=all_lines[-1][1] if all_lines else 0,
            depth=0,
            sort_order=1,
            section_type="whole",
        )]

    return result


def build_hierarchy(flat_sections: list[Section]) -> list[Section]:
    """
    평면 섹션 리스트를 depth 기반 계층 트리로 변환.
    Returns: 최상위 섹션 리스트 (children에 하위 포함)
    """
    if not flat_sections:
        return []

    roots: list[Section] = []
    stack: list[Section] = []

    for sec in flat_sections:
        # 스택에서 현재 depth보다 깊거나 같은 것 제거
        while stack and stack[-1].depth >= sec.depth:
            stack.pop()

        if stack:
            stack[-1].children.append(sec)
        else:
            roots.append(sec)

        stack.append(sec)

    return roots
