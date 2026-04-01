"""
통합 문서 파서 디스패처

파일 확장자에 따라 적절한 파서를 선택하고,
section_detector로 조항 구조를 감지한 뒤 결과를 반환한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from parsers.section_detector import RawSection, Section, detect_sections


def parse_document(file_path: str | Path) -> tuple[list[Section], int, Optional[str]]:
    """
    문서 파일을 파싱하여 섹션 트리 반환.

    Args:
        file_path: 문서 파일 경로

    Returns:
        (sections, total_pages, error_message)
        - sections: 감지된 Section 리스트
        - total_pages: 전체 페이지 수
        - error_message: 오류 시 메시지, 성공 시 None
    """
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    try:
        if ext == ".pdf":
            from parsers.pdf_parser import parse_pdf
            raw_sections, total_pages = parse_pdf(file_path)

        elif ext in (".docx", ".doc"):
            from parsers.docx_parser import parse_docx
            raw_sections, total_pages = parse_docx(file_path)

        elif ext in (".hwp", ".hwpx"):
            from parsers.hwp_parser import parse_hwp
            raw_sections, total_pages = parse_hwp(file_path)

        else:
            return [], 0, f"지원하지 않는 형식: {ext}"

        if not raw_sections:
            return [], total_pages, "텍스트를 추출할 수 없습니다."

        # 섹션 감지
        sections = detect_sections(raw_sections)
        return sections, total_pages, None

    except ImportError as e:
        return [], 0, f"필요한 라이브러리 미설치: {e}"

    except Exception as e:
        error_type = type(e).__name__
        if "UnsupportedFormat" in error_type:
            return [], 0, str(e)
        return [], 0, f"파싱 오류: {e}"
