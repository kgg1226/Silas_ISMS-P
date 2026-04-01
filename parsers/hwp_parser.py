"""
HWP 문서 파서 — 베스트에포트 구현

HWP5 (OLE2 형식) 파일에서 텍스트 추출 시도.
실패 시 parse_status='unsupported' 반환.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from parsers.section_detector import RawSection


def parse_hwp(file_path: str | Path) -> tuple[list[RawSection], int]:
    """
    HWP 파일에서 텍스트 추출 시도.
    olefile 사용 가능하면 바이너리 텍스트 추출,
    아니면 UnsupportedFormatError 발생.

    Returns:
        (raw_sections, estimated_pages)

    Raises:
        UnsupportedFormatError: HWP 파싱 불가 시
    """
    file_path = Path(file_path)

    # .hwpx (ZIP 기반)
    if file_path.suffix.lower() == ".hwpx":
        return _parse_hwpx(file_path)

    # .hwp (OLE2 기반)
    try:
        import olefile
    except ImportError:
        raise UnsupportedFormatError(
            "HWP 파싱에 olefile이 필요합니다. pip install olefile"
        )

    if not olefile.isOleFile(str(file_path)):
        raise UnsupportedFormatError("유효한 HWP(OLE2) 파일이 아닙니다.")

    try:
        ole = olefile.OleFileIO(str(file_path))

        # HWP 바이너리에서 텍스트 스트림 추출
        text_parts: list[str] = []
        for stream_name in ole.listdir():
            name = "/".join(stream_name)
            if "bodytext" in name.lower() or "section" in name.lower():
                data = ole.openstream(stream_name).read()
                # HWP 바이너리 텍스트는 UTF-16LE 또는 EUC-KR
                for encoding in ("utf-16-le", "euc-kr", "cp949", "utf-8"):
                    try:
                        decoded = data.decode(encoding, errors="ignore")
                        # 제어 문자 제거
                        clean = "".join(
                            c for c in decoded
                            if c.isprintable() or c in ("\n", "\r", "\t", " ")
                        )
                        if len(clean.strip()) > 20:
                            text_parts.append(clean.strip())
                            break
                    except Exception:
                        continue

        ole.close()

        if not text_parts:
            raise UnsupportedFormatError("HWP에서 텍스트를 추출할 수 없습니다.")

        full_text = "\n\n".join(text_parts)
        lines = full_text.count("\n") + 1
        pages = max(1, lines // 40)

        return [RawSection(text=full_text, page_number=1)], pages

    except UnsupportedFormatError:
        raise
    except Exception as e:
        raise UnsupportedFormatError(f"HWP 파싱 오류: {e}")


def _parse_hwpx(file_path: Path) -> tuple[list[RawSection], int]:
    """HWPX (ZIP 형식) 파싱 시도."""
    import zipfile
    import xml.etree.ElementTree as ET

    try:
        with zipfile.ZipFile(str(file_path), "r") as zf:
            text_parts: list[str] = []

            for name in zf.namelist():
                if "section" in name.lower() and name.endswith(".xml"):
                    data = zf.read(name)
                    root = ET.fromstring(data)
                    # HWPX XML에서 텍스트 노드 추출
                    for elem in root.iter():
                        if elem.text and elem.text.strip():
                            text_parts.append(elem.text.strip())

            if not text_parts:
                raise UnsupportedFormatError("HWPX에서 텍스트를 추출할 수 없습니다.")

            full_text = "\n".join(text_parts)
            lines = full_text.count("\n") + 1
            pages = max(1, lines // 40)

            return [RawSection(text=full_text, page_number=1)], pages

    except UnsupportedFormatError:
        raise
    except Exception as e:
        raise UnsupportedFormatError(f"HWPX 파싱 오류: {e}")


class UnsupportedFormatError(Exception):
    """파싱 불가 형식."""
    pass
