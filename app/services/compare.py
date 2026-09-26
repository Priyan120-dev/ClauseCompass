"""Document comparison service aligning clauses between two versions with automatic fallback."""
import logging

from app.llm.base import LLMClient
from app.llm.fake import FakeLLMClient
from app.models.schemas import (
    CompareResponse,
    LanguageEnum,
    ParagraphChunk,
    RoleEnum,
)
from app.services.verifier import verify_citations

logger = logging.getLogger(__name__)


async def execute_compare(
    llm_client: LLMClient,
    paragraphs_a: list[ParagraphChunk],
    paragraphs_b: list[ParagraphChunk],
    role: RoleEnum = RoleEnum.GENERIC,
    language: LanguageEnum = LanguageEnum.ENGLISH,
    doc_a_name: str = "Document A (Original)",
    doc_b_name: str = "Document B (Revised)",
) -> CompareResponse:
    """Compare two sets of document paragraphs and return aligned differences with automatic fallback."""
    try:
        response = await llm_client.compare_documents(
            paragraphs_a=paragraphs_a,
            paragraphs_b=paragraphs_b,
            role=role,
            language=language,
            doc_a_name=doc_a_name,
            doc_b_name=doc_b_name,
        )
    except Exception as exc:
        logger.warning(f"Primary LLM compare call failed ({exc}). Engaging automatic Demo fallback.")
        fallback_client = FakeLLMClient()
        response = await fallback_client.compare_documents(
            paragraphs_a=paragraphs_a,
            paragraphs_b=paragraphs_b,
            role=role,
            language=language,
            doc_a_name=doc_a_name,
            doc_b_name=doc_b_name,
        )

    # Deterministically verify evidence for each comparison item
    for item in response.items:
        if item.doc_a_evidence:
            item.doc_a_evidence, _ = verify_citations(item.doc_a_evidence, paragraphs_a)
        if item.doc_b_evidence:
            item.doc_b_evidence, _ = verify_citations(item.doc_b_evidence, paragraphs_b)

    return response
