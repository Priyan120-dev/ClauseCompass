"""Unit tests for grounded question answering service."""
import pytest

from app.llm.fake import FakeLLMClient
from app.models.schemas import QAStatusEnum, RoleEnum, VerificationStatusEnum
from app.services.chunker import chunk_document
from app.services.qa import execute_grounded_qa, retrieve_relevant_paragraphs


@pytest.fixture
def rental_paragraphs():
    with open("samples/rental_agreement.txt", encoding="utf-8") as f:
        text = f.read()
    return chunk_document([(1, text)])


def test_bm25_retrieval(rental_paragraphs):
    query = "landlord enter apartment notice"
    results = retrieve_relevant_paragraphs(query, rental_paragraphs, top_k=2)
    assert len(results) >= 1
    # Should retrieve the entry paragraph
    top_text = results[0].text.lower()
    assert "enter" in top_text or "access" in top_text


@pytest.mark.asyncio
async def test_qa_answered_with_verified_citation(rental_paragraphs):
    client = FakeLLMClient()
    response = await execute_grounded_qa(
        llm_client=client,
        paragraphs=rental_paragraphs,
        question="Can the landlord enter my premises without notice?",
        role=RoleEnum.TENANT,
    )
    assert response.status == QAStatusEnum.ANSWERED
    assert len(response.citations) > 0
    assert response.citations[0].verification_status == VerificationStatusEnum.VERIFIED
    assert "without prior written notice" in response.citations[0].exact_quote


@pytest.mark.asyncio
async def test_qa_not_determinable_for_unmentioned_facts(rental_paragraphs):
    client = FakeLLMClient()
    response = await execute_grounded_qa(
        llm_client=client,
        paragraphs=rental_paragraphs,
        question="Are pets like dogs or cats allowed in the building?",
        role=RoleEnum.TENANT,
    )
    assert response.status == QAStatusEnum.NOT_DETERMINABLE
    assert "cannot be determined from this document" in response.answer.lower()
    assert response.whats_missing_or_to_ask is not None
