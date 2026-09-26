"""Deterministic pure-Python quote verification engine with fuzzy repair step."""
import difflib
import re

from app.models.schemas import (
    ClauseAnalysis,
    EvidenceQuote,
    ParagraphChunk,
    VerificationStatusEnum,
)


def normalize_quote_text(text: str) -> str:
    """Normalize quotes, dashes, and whitespace for robust deterministic matching."""
    if not text:
        return ""
    # Normalize unicode double quotes
    text = re.sub(r'[\u201c\u201d\u201e\u00ab\u00bb\u2033]', '"', text)
    # Normalize unicode single quotes / apostrophes
    text = re.sub(r'[\u2018\u2019\u201a\u2039\u203a\u2032]', "'", text)
    # Normalize dashes and hyphens
    text = re.sub(r'[\u2013\u2014\u2015\u2212]', '-', text)
    # Normalize non-breaking spaces
    text = text.replace('\xa0', ' ').replace('\u200b', '')
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fuzzy_repair_quote(norm_quote: str, target_para_text: str, threshold: float = 0.9) -> tuple[str, float] | None:
    """Snap quote to the closest matching span in target paragraph if similarity >= threshold."""
    norm_para = normalize_quote_text(target_para_text)
    words_quote = norm_quote.split()
    words_para = norm_para.split()
    n_words = len(words_quote)

    if n_words == 0 or len(words_para) == 0:
        return None

    best_ratio = 0.0
    best_span = ""

    # Check sentence matches first
    sentences = re.split(r"(?<=[.!?])\s+", target_para_text)
    for sent in sentences:
        s_norm = normalize_quote_text(sent)
        ratio = difflib.SequenceMatcher(None, norm_quote.lower(), s_norm.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_span = sent.strip()

    # Also test sliding window of words (lengths n_words-1, n_words, n_words+1)
    for window_size in (n_words - 1, n_words, n_words + 1):
        if window_size < 1 or window_size > len(words_para):
            continue
        for i in range(len(words_para) - window_size + 1):
            candidate = " ".join(words_para[i : i + window_size])
            ratio = difflib.SequenceMatcher(None, norm_quote.lower(), candidate.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_span = candidate

    if best_ratio >= threshold:
        return best_span, best_ratio

    return None


def verify_evidence_quote(
    quote: EvidenceQuote,
    para_map: dict[str, ParagraphChunk],
    repair_threshold: float = 0.9,
) -> EvidenceQuote:
    """Deterministically verify whether exact_quote exists inside cited paragraph.
    
    If exact match fails, attempts a repair step using difflib with similarity >= repair_threshold (0.9).
    """
    target_para = para_map.get(quote.paragraph_id)
    if not target_para:
        quote.verification_status = VerificationStatusEnum.PARAGRAPH_NOT_FOUND
        quote.verification_details = f"Paragraph '{quote.paragraph_id}' does not exist in the document."
        return quote

    raw_quote = quote.exact_quote.strip()
    if not raw_quote:
        quote.verification_status = VerificationStatusEnum.ALTERED_QUOTE
        quote.verification_details = "Quote is empty."
        return quote

    norm_quote = normalize_quote_text(raw_quote)
    norm_para = normalize_quote_text(target_para.text)

    # 1. Exact verbatim normalized match
    if norm_quote in norm_para:
        quote.verification_status = VerificationStatusEnum.VERIFIED
        quote.verification_details = "Exact verbatim substring match verified."
        return quote

    # 2. Case-insensitive normalized match
    if norm_quote.lower() in norm_para.lower():
        quote.verification_status = VerificationStatusEnum.VERIFIED
        quote.verification_details = "Quote verified (with case normalization)."
        return quote

    # 3. REPAIR STEP: Snap to closest matching span in cited paragraph (threshold >= 0.9)
    repaired = fuzzy_repair_quote(norm_quote, target_para.text, threshold=repair_threshold)
    if repaired:
        snapped_span, ratio = repaired
        quote.exact_quote = snapped_span
        quote.verification_status = VerificationStatusEnum.VERIFIED
        quote.verification_details = f"Quote verified (snapped to closest match: {int(ratio * 100)}% match)."
        return quote

    # 4. Check if quote was cited under wrong paragraph
    for other_pid, other_para in para_map.items():
        if other_pid == quote.paragraph_id:
            continue
        other_norm = normalize_quote_text(other_para.text)
        if norm_quote.lower() in other_norm.lower():
            quote.verification_status = VerificationStatusEnum.PARAGRAPH_NOT_FOUND
            quote.verification_details = f"Quote not found in cited {quote.paragraph_id}, but found in {other_pid}."
            return quote

    # 5. If neither exact, repaired, nor in another paragraph, it is altered or unverified
    quote.verification_status = VerificationStatusEnum.ALTERED_QUOTE
    quote.verification_details = "Quote could not be verified in the cited paragraph."
    return quote


def verify_clauses(
    clauses: list[ClauseAnalysis],
    paragraphs: list[ParagraphChunk],
    repair_threshold: float = 0.9,
) -> tuple[list[ClauseAnalysis], float]:
    """Verify all evidence quotes across clauses and calculate the overall verification score."""
    para_map: dict[str, ParagraphChunk] = {p.paragraph_id: p for p in paragraphs}
    total_quotes = 0
    verified_quotes = 0

    for clause in clauses:
        for ev in clause.evidence:
            total_quotes += 1
            verify_evidence_quote(ev, para_map, repair_threshold=repair_threshold)
            if ev.verification_status == VerificationStatusEnum.VERIFIED:
                verified_quotes += 1

    if total_quotes == 0:
        score = 100.0
    else:
        score = round((verified_quotes / total_quotes) * 100.0, 1)

    return clauses, score


def verify_citations(
    citations: list[EvidenceQuote],
    paragraphs: list[ParagraphChunk],
    repair_threshold: float = 0.9,
) -> tuple[list[EvidenceQuote], float]:
    """Verify standalone citations for Q&A answers with repair step."""
    para_map: dict[str, ParagraphChunk] = {p.paragraph_id: p for p in paragraphs}
    total = len(citations)
    if total == 0:
        return citations, 100.0

    verified = 0
    for cit in citations:
        verify_evidence_quote(cit, para_map, repair_threshold=repair_threshold)
        if cit.verification_status == VerificationStatusEnum.VERIFIED:
            verified += 1

    score = round((verified / total) * 100.0, 1)
    return citations, score
