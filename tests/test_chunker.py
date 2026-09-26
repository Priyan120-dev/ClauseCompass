"""Unit tests for the chunker service."""
from app.services.chunker import chunk_document, normalize_whitespace


def test_normalize_whitespace():
    raw = "Hello   world!\n\nThis   is  a\ttest.\xa0Special space."
    normalized = normalize_whitespace(raw)
    assert "   " not in normalized
    assert "Hello world!" in normalized
    assert "Special space." in normalized


def test_chunk_document_basic():
    pages = [
        (1, "Paragraph one about rent.\n\nParagraph two about security deposit."),
        (2, "Paragraph three on page two about termination."),
    ]
    chunks = chunk_document(pages)
    assert len(chunks) == 3
    assert chunks[0].paragraph_id == "p1"
    assert chunks[0].page_num == 1
    assert "rent" in chunks[0].text

    assert chunks[1].paragraph_id == "p2"
    assert chunks[1].page_num == 1
    assert "security deposit" in chunks[1].text

    assert chunks[2].paragraph_id == "p3"
    assert chunks[2].page_num == 2
    assert "termination" in chunks[2].text
    assert chunks[2].token_count > 0


def test_chunk_document_handles_empty():
    chunks = chunk_document([(1, ""), (2, "   \n\n  ")])
    assert len(chunks) == 0


def test_chunk_document_long_numbered_split():
    long_text = "Introductory text.\n\n" + (
        "1. First sub section of the contract with significant text detailing the payment terms.\n"
        + " " * 50
        + "2. Second sub section of the contract with detailed terms on warranties and liabilities.\n"
        + " " * 1200
    )
    pages = [(1, long_text)]
    chunks = chunk_document(pages)
    assert len(chunks) >= 2
