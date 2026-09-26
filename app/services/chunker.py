"""Paragraph splitting and canonical chunk generation."""
import re

from app.models.schemas import ParagraphChunk

_SPACES_TABS_RE = re.compile(r"[ \t]+")
_DOUBLE_NEWLINE_RE = re.compile(r"\n\s*\n+")
_SUB_SECTION_RE = re.compile(r"(?=(?:^|\n)\s*(?:\d+\.|\bSECTION\s+\d+:|\bARTICLE\s+\d+:))")


def normalize_whitespace(text: str) -> str:
    """Normalize repeated whitespace while keeping sentence structure clean."""
    # Replace non-breaking spaces and other unicode spaces
    text = text.replace("\xa0", " ").replace("\u200b", "")
    # Normalize multiple spaces and tabs to single space using precompiled regex
    lines = [_SPACES_TABS_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def chunk_document(pages_text: list[tuple[int, str]]) -> list[ParagraphChunk]:
    """Chunk document text into paragraphs with stable sequential IDs."""
    chunks: list[ParagraphChunk] = []
    global_seq = 1

    for page_num, page_content in pages_text:
        normalized = normalize_whitespace(page_content)
        if not normalized:
            continue

        # Split on double newlines using precompiled regex
        raw_paras = _DOUBLE_NEWLINE_RE.split(normalized)

        for p_str in raw_paras:
            p_str = p_str.strip()
            if not p_str:
                continue

            # If a paragraph is exceptionally long (e.g. > 1500 chars) and contains numbered sections, split further
            if len(p_str) > 1200:
                sub_sections = _SUB_SECTION_RE.split(p_str)
                if len(sub_sections) > 1:
                    for sub in sub_sections:
                        sub = sub.strip()
                        if sub:
                            token_est = max(1, len(sub) // 4)
                            chunks.append(
                                ParagraphChunk(
                                    paragraph_id=f"p{global_seq}",
                                    page_num=page_num,
                                    text=sub,
                                    token_count=token_est,
                                )
                            )
                            global_seq += 1
                    continue

            token_est = max(1, len(p_str) // 4)
            chunks.append(
                ParagraphChunk(
                    paragraph_id=f"p{global_seq}",
                    page_num=page_num,
                    text=p_str,
                    token_count=token_est,
                )
            )
            global_seq += 1

    return chunks
