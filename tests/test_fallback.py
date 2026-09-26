"""Unit tests for automatic fallback mechanism when LLM encounters 429/timeout/error."""
import pytest

from app.llm.base import LLMClient
from app.models.schemas import (
    LanguageEnum,
    ParagraphChunk,
    ReadingLevelEnum,
    RoleEnum,
)
from app.services.analyzer import analyze_document_pipeline
from app.services.compare import execute_compare
from app.services.qa import execute_grounded_qa


class FailingLLMClient(LLMClient):
    """Simulates an LLM client throwing 429 Quota Exceeded or Connection Timeout."""

    async def analyze_document(
        self,
        paragraphs,
        role=RoleEnum.GENERIC,
        language=LanguageEnum.ENGLISH,
        reading_level=ReadingLevelEnum.STANDARD,
        doc_type="generic",
    ):
        raise RuntimeError("429 Resource Exhausted: Quota exceeded for Gemini API call")

    async def answer_question(
        self,
        paragraphs,
        question,
        role=RoleEnum.GENERIC,
        language=LanguageEnum.ENGLISH,
    ):
        raise TimeoutError("LLM API request timed out after 30 seconds")

    async def compare_documents(
        self,
        paragraphs_a,
        paragraphs_b,
        role=RoleEnum.GENERIC,
        language=LanguageEnum.ENGLISH,
        doc_a_name="Doc A",
        doc_b_name="Doc B",
    ):
        raise ConnectionError("Failed to establish SSL connection to Gemini endpoint")


@pytest.fixture
def sample_pages():
    with open("samples/rental_agreement.txt", encoding="utf-8") as f:
        text = f.read()
    return [(1, text)]


@pytest.fixture
def sample_paragraphs():
    return [
        ParagraphChunk(
            paragraph_id="p1",
            page_num=1,
            text="Tenant agrees to pay monthly rent in the amount of $2,400.00 USD on the 1st day of each month.",
            token_count=20,
        )
    ]


@pytest.mark.asyncio
async def test_analyzer_automatic_fallback_on_429(sample_pages):
    failing_client = FailingLLMClient()
    response = await analyze_document_pipeline(
        llm_client=failing_client,
        pages_text=sample_pages,
        role=RoleEnum.TENANT,
        doc_type="rental",
        use_cache=False,
    )
    assert response.llm_backend == "Demo (fallback)"
    assert response.total_clauses > 0
    assert response.verification_score > 70.0


@pytest.mark.asyncio
async def test_qa_automatic_fallback_on_timeout(sample_paragraphs):
    failing_client = FailingLLMClient()
    response = await execute_grounded_qa(
        llm_client=failing_client,
        paragraphs=sample_paragraphs,
        question="When is rent due?",
        role=RoleEnum.TENANT,
    )
    assert response.answer is not None
    assert len(response.answer) > 0


@pytest.mark.asyncio
async def test_compare_automatic_fallback_on_connection_error(sample_paragraphs):
    failing_client = FailingLLMClient()
    response = await execute_compare(
        llm_client=failing_client,
        paragraphs_a=sample_paragraphs,
        paragraphs_b=sample_paragraphs,
        role=RoleEnum.FREELANCER,
    )
    assert response.total_differences >= 1
    assert len(response.items) >= 1
