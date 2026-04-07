"""
입력 검증 유틸리티 모듈.

폼 데이터 및 경로 파라미터의 유효성을 검증한다.
위반 시 ValidationError를 발생시키며, 라우트 레이어에서 잡아 사용자에게 전달한다.
"""
from __future__ import annotations

import re
from typing import Iterable


class ValidationError(ValueError):
    """입력 검증 실패."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


# ---------------------------------------------------------------------------
# 문서 관련
# ---------------------------------------------------------------------------
ALLOWED_DOC_TYPES = (
    "정책서", "지침서", "절차서", "계획서", "보고서",
    "회의록", "승인문서", "매뉴얼", "기타",
)

ALLOWED_DOC_STATUS = (
    "draft", "active", "expired", "superseded", "archived",
)

ALLOWED_FILE_EXTENSIONS = (
    ".pdf", ".docx", ".doc", ".hwp", ".hwpx", ".txt", ".md",
)

MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def validate_doc_type(value: str) -> str:
    if not value:
        raise ValidationError("doc_type", "문서 유형은 필수입니다")
    if value not in ALLOWED_DOC_TYPES:
        raise ValidationError(
            "doc_type",
            f"허용되지 않는 문서 유형. 가능: {', '.join(ALLOWED_DOC_TYPES)}",
        )
    return value


def validate_doc_status(value: str) -> str:
    if value not in ALLOWED_DOC_STATUS:
        raise ValidationError(
            "status",
            f"허용되지 않는 상태. 가능: {', '.join(ALLOWED_DOC_STATUS)}",
        )
    return value


def validate_file_upload(file_name: str, file_size: int) -> None:
    if not file_name:
        raise ValidationError("file", "파일명이 비어 있습니다")

    ext = _get_extension(file_name)
    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise ValidationError(
            "file",
            f"허용되지 않는 확장자 '{ext}'. 가능: {', '.join(ALLOWED_FILE_EXTENSIONS)}",
        )

    if file_size <= 0:
        raise ValidationError("file", "빈 파일입니다")
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            "file",
            f"파일 크기 초과: {file_size / (1024*1024):.1f}MB > {MAX_FILE_SIZE_MB}MB",
        )


def _get_extension(file_name: str) -> str:
    idx = file_name.rfind(".")
    if idx < 0:
        return ""
    return file_name[idx:].lower()


# ---------------------------------------------------------------------------
# ISMS-P 항목 코드
# ---------------------------------------------------------------------------
# 예: 1.1.1, 2.10.3 (숫자.숫자.숫자)
ITEM_CODE_PATTERN = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{1,2}$")


def validate_item_code(value: str) -> str:
    if not value:
        raise ValidationError("item_code", "항목 코드는 필수입니다")
    if not ITEM_CODE_PATTERN.match(value):
        raise ValidationError(
            "item_code",
            f"잘못된 형식 '{value}'. 예: 1.1.1",
        )
    return value


# ---------------------------------------------------------------------------
# 매핑 관련
# ---------------------------------------------------------------------------
ALLOWED_COVERAGE_LEVELS = ("full", "partial", "reference")
ALLOWED_FULFILLMENT_TYPES = ("document", "system", "mixed")


def validate_coverage_level(value: str) -> str:
    if value not in ALLOWED_COVERAGE_LEVELS:
        raise ValidationError(
            "coverage_level",
            f"허용되지 않음. 가능: {', '.join(ALLOWED_COVERAGE_LEVELS)}",
        )
    return value


def validate_fulfillment_type(value: str) -> str:
    if value not in ALLOWED_FULFILLMENT_TYPES:
        raise ValidationError(
            "fulfillment_type",
            f"허용되지 않음. 가능: {', '.join(ALLOWED_FULFILLMENT_TYPES)}",
        )
    return value


# ---------------------------------------------------------------------------
# 일반 유틸
# ---------------------------------------------------------------------------
def validate_one_of(value: str, allowed: Iterable[str], field: str) -> str:
    allowed_tuple = tuple(allowed)
    if value not in allowed_tuple:
        raise ValidationError(
            field,
            f"허용되지 않는 값 '{value}'. 가능: {', '.join(allowed_tuple)}",
        )
    return value
