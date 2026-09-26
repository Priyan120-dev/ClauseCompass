"""Validation utilities for file uploads, sizes, magic bytes, and page limits."""
import io

from docx import Document
from fastapi import HTTPException, status
from pypdf import PdfReader

from app.config import settings

# Magic byte signatures
PDF_MAGIC = b"%PDF-"
ZIP_DOCX_MAGIC = b"PK\x03\x04"


def validate_file_size(content: bytes) -> None:
    """Validate that file content does not exceed maximum allowed size."""
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.max_file_size_mb} MB.",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )


def detect_and_validate_format(filename: str, content: bytes) -> str:
    """Detect format from filename and verify against magic bytes.
    
    Returns normalized format: 'pdf', 'docx', or 'txt'.
    """
    fn_lower = filename.lower()

    if fn_lower.endswith(".pdf"):
        if not content.startswith(PDF_MAGIC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file: Missing %PDF- magic bytes signature.",
            )
        return "pdf"

    if fn_lower.endswith(".docx"):
        if not content.startswith(ZIP_DOCX_MAGIC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid DOCX file: Missing PK ZIP magic bytes signature.",
            )
        return "docx"

    if fn_lower.endswith(".txt") or fn_lower.endswith(".md"):
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content.decode("latin-1")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Text file could not be decoded as valid UTF-8 or Latin-1.",
                )
        return "txt"

    # If extension is ambiguous, check magic bytes directly
    if content.startswith(PDF_MAGIC):
        return "pdf"
    if content.startswith(ZIP_DOCX_MAGIC):
        return "docx"

    # Default to text if decodable
    try:
        content.decode("utf-8")
        return "txt"
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file format. Please upload PDF, DOCX, or TXT files.",
        )


def validate_pdf_pages(content: bytes) -> int:
    """Validate that PDF has at most max_pages and return page count."""
    try:
        reader = PdfReader(io.BytesIO(content))
        page_count = len(reader.pages)
        if page_count > settings.max_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PDF document exceeds page limit: {page_count} pages (limit is {settings.max_pages}).",
            )
        return page_count
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse PDF document: {str(e)}",
        )


def validate_docx_content(content: bytes) -> int:
    """Validate DOCX can be opened and estimate page count."""
    try:
        doc = Document(io.BytesIO(content))
        para_count = len(doc.paragraphs)
        # Approximate: ~10 paragraphs per page
        estimated_pages = max(1, para_count // 10)
        if estimated_pages > settings.max_pages * 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DOCX document exceeds page limit (estimated {estimated_pages} pages).",
            )
        return estimated_pages
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse DOCX document: {str(e)}",
        )
