"""Document ingestion service for PDF, DOCX, TXT, and raw text."""
import io

from app.security.validation import (
    detect_and_validate_format,
    validate_docx_content,
    validate_file_size,
    validate_pdf_pages,
)


def extract_text_from_bytes(filename: str, content: bytes) -> list[tuple[int, str]]:
    """Extract text from file bytes with page tracking.
    
    Returns a list of (page_num, page_or_section_text) tuples.
    """
    validate_file_size(content)
    file_type = detect_and_validate_format(filename, content)

    if file_type == "pdf":
        validate_pdf_pages(content)
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages_text: list[tuple[int, str]] = []
        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append((idx, text))
        return pages_text

    elif file_type == "docx":
        validate_docx_content(content)
        from docx import Document
        doc = Document(io.BytesIO(content))
        paragraphs: list[str] = []
        for p in doc.paragraphs:
            if p.text.strip():
                paragraphs.append(p.text.strip())
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        full_text = "\n\n".join(paragraphs)
        return [(1, full_text)]

    else:  # txt or plain text
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
        return [(1, text)]


def extract_text_from_raw_string(text: str) -> list[tuple[int, str]]:
    """Convert raw pasted string into page blocks."""
    if not text.strip():
        return []
    # If text contains page markers (e.g. --- Page 2 --- or \f form feed)
    if "\f" in text:
        pages = text.split("\f")
        return [(idx, p.strip()) for idx, p in enumerate(pages, start=1) if p.strip()]
    return [(1, text.strip())]
