"""
PDF 문서 파서 — pdfplumber 사용
페이지별 텍스트 추출 후 RawSection 리스트 반환.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from parsers.section_detector import RawSection


def parse_pdf(file_path: str | Path) -> tuple[list[RawSection], int]:
    """
    PDF 파일에서 페이지별 텍스트 추출.

    Returns:
        (raw_sections, total_pages)
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "pdfplumber가 설치되지 않았습니다. pip install pdfplumber"
        )

    raw_sections: list[RawSection] = []

    with pdfplumber.open(str(file_path)) as pdf:
        total_pages = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                raw_sections.append(RawSection(
                    text=text.strip(),
                    page_number=i + 1,
                ))

    return raw_sections, total_pages
