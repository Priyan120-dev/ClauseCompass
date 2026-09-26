"""Grounded Q&A service with paragraph retrieval, deterministic verification, and automatic fallback."""
import logging
import math
import re
from collections import Counter, OrderedDict
from functools import lru_cache

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


_TOKEN_RE = re.compile(r"\b[a-zA-Z0-9$%'_-]+\b")


@lru_cache(maxsize=4096)
def tokenize(text: str) -> list[str]:
    """Tokenize string into lowercase alphanumeric words (cached)."""
    return [w for w in _TOKEN_RE.findall(text.lower()) if w not in STOP_WORDS]


class CorpusIndex:
    """Precomputed token and term frequency index for BM25 retrieval over a paragraph collection."""

    __slots__ = ("paragraphs", "para_token_lists", "para_tf_list", "doc_freq", "total_len", "avg_len", "num_docs")

    def __init__(self, paragraphs: list[ParagraphChunk]):
        self.paragraphs = paragraphs
        self.para_token_lists: list[list[str]] = []
        self.para_tf_list: list[Counter] = []
        self.doc_freq: Counter = Counter()
        self.total_len: int = 0
        self.num_docs: int = len(paragraphs)

        for p in paragraphs:
            tokens = tokenize(p.text)
            self.para_token_lists.append(tokens)
            self.total_len += len(tokens)
            self.para_tf_list.append(Counter(tokens))
            for unique_term in set(tokens):
                self.doc_freq[unique_term] += 1

        self.avg_len: float = self.total_len / max(1, self.num_docs)


class CorpusIndexCache:
    """LRU cache of pre-indexed document corpora to avoid repeated re-tokenization per session."""

    def __init__(self, capacity: int = 32):
        self.capacity = capacity
        self.cache: OrderedDict[str, CorpusIndex] = OrderedDict()

    def _make_key(self, paragraphs: list[ParagraphChunk]) -> str:
        if not paragraphs:
            return ""
        p_first = paragraphs[0]
        p_last = paragraphs[-1]
        sample_hash = hash((
            len(p_first.text),
            len(p_last.text),
            p_first.paragraph_id,
            p_last.paragraph_id,
            len(paragraphs),
        ))
        return f"{len(paragraphs)}:{p_first.paragraph_id}:{p_last.paragraph_id}:{sample_hash}"

    def get_or_build(self, paragraphs: list[ParagraphChunk]) -> CorpusIndex:
        if not paragraphs:
            return CorpusIndex([])
        key = self._make_key(paragraphs)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        idx = CorpusIndex(paragraphs)
        self.cache[key] = idx
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
        return idx


_corpus_cache = CorpusIndexCache(capacity=32)


def retrieve_relevant_paragraphs(
    query: str,
    paragraphs: list[ParagraphChunk],
    top_k: int = 5,
) -> list[ParagraphChunk]:
    """Retrieve top-K most relevant paragraphs using BM25-style term scoring with cached corpus."""
    if not paragraphs:
        return []

    q_tokens = tokenize(query)
    if not q_tokens:
        return paragraphs[:top_k]

    corpus = _corpus_cache.get_or_build(paragraphs)
    num_docs = corpus.num_docs
    avg_len = corpus.avg_len
    k1 = 1.5
    b = 0.75

    scored: list[tuple[float, ParagraphChunk]] = []

    for idx, p in enumerate(paragraphs):
        p_tokens = corpus.para_token_lists[idx]
        doc_len = len(p_tokens)
        tf = corpus.para_tf_list[idx]
        score = 0.0

        for term in q_tokens:
            if term in tf:
                df = corpus.doc_freq.get(term, 0)
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
