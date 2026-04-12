"""
문서 업로드 통합 테스트.

POST /documents/upload 엔드포인트를 TestClient로 검증한다.
- 유효한 PDF 업로드 → /documents/{id} 리다이렉트
- 허용되지 않는 확장자 → 오류 메시지
- 빈 파일 → 오류 메시지
- 잘못된 doc_type → 오류 메시지
- 업로드 후 목록 페이지에 해당 문서 표시 확인
"""
from __future__ import annotations

import io


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload(client, *, filename="test.pdf", content=b"%PDF-1.4 test", doc_type="정책서",
            title="테스트 정책서", follow_redirects=False, **extra_fields):
    """POST /documents/upload 헬퍼."""
    data = {
        "title": title,
        "doc_type": doc_type,
        "version": "1.0",
        "author": "테스터",
        **extra_fields,
    }
    files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
    return client.post(
        "/documents/upload",
        data=data,
        files=files,
        follow_redirects=follow_redirects,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_upload_valid_pdf(test_client):
    """유효한 PDF 업로드 시 /documents/{id} 로 303 리다이렉트."""
    resp = _upload(test_client, filename="policy.pdf", content=b"%PDF-1.4 test content")
    assert resp.status_code == 303, f"Expected 303, got {resp.status_code}"
    location = resp.headers.get("location", "")
    # 리다이렉트 대상이 /documents/<숫자> 형식이어야 한다
    assert location.startswith("/documents/"), (
        f"Expected redirect to /documents/{{id}}, got '{location}'"
    )
    doc_id_part = location.split("/documents/")[-1]
    assert doc_id_part.isdigit(), (
        f"Expected numeric doc id in redirect, got '{doc_id_part}'"
    )


def test_upload_invalid_extension(test_client):
    """.exe 파일 업로드 시 오류 메시지가 응답에 포함되어야 한다."""
    resp = _upload(
        test_client,
        filename="malware.exe",
        content=b"MZ\x90\x00 fake exe content",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    text = resp.text
    # 확장자 관련 오류 키워드 확인
    assert any(kw in text for kw in ("허용되지 않는", "확장자", ".exe", "가능")), (
        f"Expected extension error message in response, got: {text[:500]}"
    )


def test_upload_empty_file(test_client):
    """0바이트 파일 업로드 시 빈 파일 오류 메시지가 응답에 포함되어야 한다."""
    resp = _upload(
        test_client,
        filename="empty.pdf",
        content=b"",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    text = resp.text
    assert any(kw in text for kw in ("빈 파일", "비어", "크기", "오류", "error")), (
        f"Expected empty-file error message in response, got: {text[:500]}"
    )


def test_upload_invalid_doc_type(test_client):
    """허용되지 않는 doc_type 업로드 시 오류 메시지가 응답에 포함되어야 한다."""
    resp = _upload(
        test_client,
        filename="valid.pdf",
        content=b"%PDF-1.4 valid content",
        doc_type="invalid",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    text = resp.text
    assert any(kw in text for kw in ("허용되지 않는", "문서 유형", "가능", "doc_type")), (
        f"Expected doc_type error message in response, got: {text[:500]}"
    )


def test_document_list_after_upload(test_client):
    """업로드 성공 후 GET /documents 목록에 해당 문서 제목이 표시되어야 한다."""
    unique_title = "통합테스트_목록확인_문서_2026"

    # 업로드
    upload_resp = _upload(
        test_client,
        filename="list_check.pdf",
        content=b"%PDF-1.4 list check content",
        title=unique_title,
        doc_type="지침서",
    )
    assert upload_resp.status_code == 303, (
        f"Upload should redirect (303), got {upload_resp.status_code}"
    )

    # 목록 조회
    list_resp = test_client.get("/documents")
    assert list_resp.status_code == 200
    assert unique_title in list_resp.text, (
        f"Uploaded document title '{unique_title}' not found in /documents response"
    )


def test_upload_then_detail_page(test_client):
    """업로드 후 /documents/{id} 상세 페이지가 문서 제목을 포함해 렌더링되어야 한다."""
    unique_title = "통합테스트_상세페이지_E2E_2026"

    upload_resp = _upload(
        test_client,
        filename="e2e_detail.pdf",
        content=b"%PDF-1.4 e2e detail test",
        title=unique_title,
        doc_type="매뉴얼",
    )
    assert upload_resp.status_code == 303

    # 리다이렉트 URL에서 doc_id 추출
    location = upload_resp.headers["location"]
    doc_id = location.split("/documents/")[-1]
    assert doc_id.isdigit(), f"Expected numeric doc_id, got '{doc_id}'"

    # 상세 페이지 접근
    detail_resp = test_client.get(f"/documents/{doc_id}")
    assert detail_resp.status_code == 200
    assert unique_title in detail_resp.text, (
        f"Document title '{unique_title}' not found on detail page"
    )


def test_upload_then_parse_trigger(test_client):
    """업로드 후 POST /documents/{id}/parse 가 오류 없이 303을 반환해야 한다."""
    upload_resp = _upload(
        test_client,
        filename="parse_trigger.pdf",
        content=b"%PDF-1.4 parse trigger test",
        title="파싱트리거_테스트_2026",
        doc_type="보고서",
    )
    assert upload_resp.status_code == 303

    doc_id = upload_resp.headers["location"].split("/documents/")[-1]
    assert doc_id.isdigit()

    # 파싱 트리거 — 실제 파서가 실패해도 라우트는 303 리다이렉트해야 한다
    parse_resp = test_client.post(f"/documents/{doc_id}/parse", follow_redirects=False)
    assert parse_resp.status_code == 303, (
        f"Parse trigger should return 303, got {parse_resp.status_code}"
    )
