"""Unit tests for file size, magic byte verification, and safe IP extraction."""
import pytest
from fastapi import HTTPException, Request

from app.security.ratelimit import extract_client_ip
from app.security.validation import (
    detect_and_validate_format,
    validate_file_size,
)


def test_validate_file_size_ok():
    content = b"Short contract text"
    validate_file_size(content)  # Should not raise


def test_validate_file_size_empty():
    with pytest.raises(HTTPException) as exc_info:
        validate_file_size(b"")
    assert exc_info.value.status_code == 400
    assert "empty" in exc_info.value.detail.lower()


def test_validate_file_size_exceeded():
    large_bytes = b"x" * (6 * 1024 * 1024)  # 6 MB (limit is 5 MB)
    with pytest.raises(HTTPException) as exc_info:
        validate_file_size(large_bytes)
    assert exc_info.value.status_code == 413


def test_magic_bytes_pdf_valid():
    valid_pdf_start = b"%PDF-1.4 test document content"
    fmt = detect_and_validate_format("contract.pdf", valid_pdf_start)
    assert fmt == "pdf"


def test_magic_bytes_pdf_invalid():
    invalid_pdf = b"NOT_A_PDF content"
    with pytest.raises(HTTPException) as exc_info:
        detect_and_validate_format("contract.pdf", invalid_pdf)
    assert exc_info.value.status_code == 400
    assert "magic bytes" in exc_info.value.detail.lower()


def test_magic_bytes_docx_valid():
    valid_docx = b"PK\x03\x04test zip container"
    fmt = detect_and_validate_format("contract.docx", valid_docx)
    assert fmt == "docx"


def test_magic_bytes_docx_invalid():
    invalid_docx = b"PLAIN_TEXT_NOT_A_ZIP"
    with pytest.raises(HTTPException) as exc_info:
        detect_and_validate_format("contract.docx", invalid_docx)
    assert exc_info.value.status_code == 400


def test_safe_x_forwarded_for_extraction():
    class DummyClient:
        host = "10.0.0.1"

    # 1. Clean public IP in X-Forwarded-For
    req = Request(
        scope={
            "type": "http",
            "headers": [(b"x-forwarded-for", b"198.51.100.42, 10.0.0.2")],
            "client": ("10.0.0.1", 12345),
        }
    )
    assert extract_client_ip(req) == "198.51.100.42"

    # 2. Malformed / Spoofed IP falls back to socket IP
    req_malformed = Request(
        scope={
            "type": "http",
            "headers": [(b"x-forwarded-for", b"malicious_sql_or_string;DROP TABLE;")],
            "client": ("10.0.0.1", 12345),
        }
    )
    assert extract_client_ip(req_malformed) == "10.0.0.1"

    # 3. No X-Forwarded-For header uses socket IP
    req_direct = Request(
        scope={
            "type": "http",
            "headers": [],
            "client": ("192.168.1.50", 12345),
        }
    )
    assert extract_client_ip(req_direct) == "192.168.1.50"
