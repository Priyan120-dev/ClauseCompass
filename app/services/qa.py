"""Grounded Q&A service with paragraph retrieval, deterministic verification, and automatic fallback."""
import logging
import math
import re
from collections import Counter

from app.llm.base import LLMClient
from app.llm.fake import FakeLLMClient
from app.models.schemas import (
    LanguageEnum,
    ParagraphChunk,
    QAResponse,
    QAStatusEnum,
    RoleEnum,
)
from app.services.verifier import verify_citations

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "isn't", "it", "its", "itself", "let's", "me", "more", "most", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "with",
    "won't", "would", "you", "your", "yours", "yourself", "yourselves",
}


def tokenize(text: str) -> list[str]:
    """Tokenize string into lowercase alphanumeric words."""
    return [w for w in re.findall(r"\b[a-zA-Z0-9$%'_-]+\b", text.lower()) if w not in STOP_WORDS]


def retrieve_relevant_paragraphs(
    query: str,
    paragraphs: list[ParagraphChunk],
    top_k: int = 5,
) -> list[ParagraphChunk]:
    """Retrieve top-K most relevant paragraphs using BM25-style term scoring."""
    if not paragraphs:
        return []

    q_tokens = tokenize(query)
    if not q_tokens:
        return paragraphs[:top_k]

    doc_freq: Counter = Counter()
    para_token_lists = []
    total_len = 0

    for p in paragraphs:
        tokens = tokenize(p.text)
        para_token_lists.append(tokens)
        total_len += len(tokens)
        for unique_term in set(tokens):
            doc_freq[unique_term] += 1

    num_docs = len(paragraphs)
    avg_len = total_len / max(1, num_docs)
    k1 = 1.5
    b = 0.75

    scored: list[tuple[float, ParagraphChunk]] = []

    for idx, p in enumerate(paragraphs):
        p_tokens = para_token_lists[idx]
        doc_len = len(p_tokens)
        tf = Counter(p_tokens)
        score = 0.0

        for term in q_tokens:
            if term in tf:
                df = doc_freq.get(term, 0)
                idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0)
                freq = tf[term]
                tf_norm = (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * (doc_len / max(1.0, avg_len))))
                score += idf * tf_norm

        if query.lower() in p.text.lower():
            score += 10.0

        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for score, p in scored[:top_k]]


async def execute_grounded_qa(
    llm_client: LLMClient,
    paragraphs: list[ParagraphChunk],
    question: str,
    role: RoleEnum = RoleEnum.GENERIC,
    language: LanguageEnum = LanguageEnum.ENGLISH,
) -> QAResponse:
    """Perform grounded question answering with verification and automatic fallback."""
    relevant_paras = retrieve_relevant_paragraphs(question, paragraphs, top_k=6)

    if not relevant_paras:
        return QAResponse(
            question=question,
            answer="No relevant text found in document. Cannot be determined from this document.",
            status=QAStatusEnum.NOT_DETERMINABLE,
            citations=[],
            whats_missing_or_to_ask="Please check if document content was successfully loaded.",
        )

    try:
        response = await llm_client.answer_question(
            paragraphs=relevant_paras,
            question=question,
            role=role,
            language=language,
        )
    except Exception as exc:
        logger.warning(f"Primary LLM QA call failed ({exc}). Engaging automatic Demo fallback.")
        fallback_client = FakeLLMClient()
        response = await fallback_client.answer_question(
            paragraphs=relevant_paras,
            question=question,
            role=role,
            language=language,
        )

    # Deterministically verify citations against full paragraph collection
    verified_citations, _ = verify_citations(response.citations, paragraphs)
    response.citations = verified_citations

    if response.status == QAStatusEnum.NOT_DETERMINABLE:
        if "cannot be determined" not in response.answer.lower():
            response.answer = f"{response.answer} (Cannot be determined from this document)."

    return response
