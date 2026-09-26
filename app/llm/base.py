"""Abstract base class for LLM client implementations."""
from abc import ABC, abstractmethod

from app.models.schemas import (
    ClauseAnalysis,
    CompareResponse,
    LanguageEnum,
    ParagraphChunk,
    QAResponse,
    ReadingLevelEnum,
    RoleEnum,
)


class LLMClient(ABC):
    """Abstract interface for LLM backends (Gemini and Fake/Mock)."""

    @abstractmethod
    async def analyze_document(
        self,
        paragraphs: list[ParagraphChunk],
        role: RoleEnum = RoleEnum.GENERIC,
        language: LanguageEnum = LanguageEnum.ENGLISH,
        reading_level: ReadingLevelEnum = ReadingLevelEnum.STANDARD,
        doc_type: str = "generic",
    ) -> list[ClauseAnalysis]:
        """Analyze clauses in the document and return structured clause analyses."""
        pass

    @abstractmethod
    async def answer_question(
        self,
        paragraphs: list[ParagraphChunk],
        question: str,
        role: RoleEnum = RoleEnum.GENERIC,
        language: LanguageEnum = LanguageEnum.ENGLISH,
    ) -> QAResponse:
        """Answer a question grounded strictly in provided paragraphs."""
        pass

    @abstractmethod
    async def compare_documents(
        self,
        paragraphs_a: list[ParagraphChunk],
        paragraphs_b: list[ParagraphChunk],
        role: RoleEnum = RoleEnum.GENERIC,
        language: LanguageEnum = LanguageEnum.ENGLISH,
        doc_a_name: str = "Document A",
        doc_b_name: str = "Document B",
    ) -> CompareResponse:
        """Compare two sets of document paragraphs and return aligned differences."""
        pass
