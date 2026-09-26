"""Unit tests for the deterministic quote verification engine and repair step."""
import pytest

from app.models.schemas import (
    ClauseAnalysis,
    EvidenceQuote,
    ParagraphChunk,
    RiskLevelEnum,
    VerificationStatusEnum,
)
from app.services.verifier import (
    fuzzy_repair_quote,
    normalize_quote_text,
    verify_clauses,
    verify_evidence_quote,
)


@pytest.fixture
def sample_paragraphs():
    return [
        ParagraphChunk(
            paragraph_id="p1",
            page_num=1,
            text="Tenant agrees to pay monthly rent in the amount of $2,400.00 USD, payable in advance on or before the first (1st) day of each calendar month.",
            token_count=35,
        ),
        ParagraphChunk(
            paragraph_id="p2",
            page_num=1,
            text="Landlord may enter the Premises at any time of day or night without prior written notice to inspect the condition.",
            token_count=25,
        ),
    ]


def test_normalize_quote_text():
    text = "“Special quote” with ‘single’ dashes — and – hyphens"
    normalized = normalize_quote_text(text)
    assert '"Special quote"' in normalized
    assert "'single'" in normalized
    assert "-" in normalized


def test_verify_valid_exact_quote(sample_paragraphs):
    para_map = {p.paragraph_id: p for p in sample_paragraphs}
    quote = EvidenceQuote(
        paragraph_id="p1",
        exact_quote="monthly rent in the amount of $2,400.00 USD",
    )
    result = verify_evidence_quote(quote, para_map)
    assert result.verification_status == VerificationStatusEnum.VERIFIED
    assert "Exact verbatim" in result.verification_details


def test_verify_quote_with_unicode_and_case(sample_paragraphs):
    para_map = {p.paragraph_id: p for p in sample_paragraphs}
    quote = EvidenceQuote(
        paragraph_id="p2",
        exact_quote="LANDLORD MAY ENTER THE PREMISES AT ANY TIME",
    )
    result = verify_evidence_quote(quote, para_map)
    assert result.verification_status == VerificationStatusEnum.VERIFIED


def test_verify_fuzzy_repair_snaps_closest_match(sample_paragraphs):
    para_map = {p.paragraph_id: p for p in sample_paragraphs}
    # Slightly imperfect quote (missing trailing period or slight typo)
    imperfect_quote = EvidenceQuote(
        paragraph_id="p2",
        exact_quote="Landlord may enter the Premises at any time of day or night without prior written notice to inspect",
    )
    result = verify_evidence_quote(imperfect_quote, para_map, repair_threshold=0.85)
    assert result.verification_status == VerificationStatusEnum.VERIFIED
    assert "snapped to closest match" in result.verification_details or "Exact" in result.verification_details


def test_verify_altered_quote_fails(sample_paragraphs):
    para_map = {p.paragraph_id: p for p in sample_paragraphs}
    quote = EvidenceQuote(
        paragraph_id="p1",
        exact_quote="monthly rent in the amount of $1,000.00 USD (hallucinated amount)",
    )
    result = verify_evidence_quote(quote, para_map)
    assert result.verification_status == VerificationStatusEnum.ALTERED_QUOTE


def test_verify_wrong_paragraph_citation(sample_paragraphs):
    para_map = {p.paragraph_id: p for p in sample_paragraphs}
    # Quote from p2 cited under p1
    quote = EvidenceQuote(
        paragraph_id="p1",
        exact_quote="without prior written notice to inspect the condition",
    )
    result = verify_evidence_quote(quote, para_map)
    assert result.verification_status == VerificationStatusEnum.PARAGRAPH_NOT_FOUND
    assert "found in p2" in result.verification_details


def test_verify_clauses_score_calculation(sample_paragraphs):
    clauses = [
        ClauseAnalysis(
            clause_id="c1",
            category="Payment",
            title="Rent",
            plain_language_summary="Rent summary",
            risk_level=RiskLevelEnum.LOW,
            risk_reason="Standard",
            user_role_impact="Tenant",
            obligations=[],
            evidence=[
                EvidenceQuote(paragraph_id="p1", exact_quote="monthly rent in the amount of $2,400.00 USD"),
                EvidenceQuote(paragraph_id="p1", exact_quote="Non-existent hallucinated quote"),
            ],
        )
    ]
    verified_clauses, score = verify_clauses(clauses, sample_paragraphs)
    assert len(verified_clauses) == 1
    # 1 verified out of 2 quotes = 50.0%
    assert score == 50.0
    assert verified_clauses[0].evidence[0].verification_status == VerificationStatusEnum.VERIFIED
    assert verified_clauses[0].evidence[1].verification_status == VerificationStatusEnum.ALTERED_QUOTE


def test_fuzzy_repair_empty():
    res = fuzzy_repair_quote("", "some paragraph text")
    assert res is None
