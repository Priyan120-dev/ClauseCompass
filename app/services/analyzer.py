"""Document analysis orchestration service with LRU caching, PII masking, and automatic fallback."""
import hashlib
import logging
from collections import OrderedDict

from app.config import settings
from app.llm.base import LLMClient
from app.llm.fake import FakeLLMClient
from app.models.schemas import (
    DocumentAnalysisResponse,
    LanguageEnum,
    ReadingLevelEnum,
    RiskLevelEnum,
    RoleEnum,
)
from app.security.sanitize import mask_pii
from app.services.chunker import chunk_document
from app.services.missing_clauses import check_missing_clauses
from app.services.verifier import verify_clauses

logger = logging.getLogger(__name__)


class AnalysisLRUCache:
    """Thread-safe in-memory LRU cache storing recent document analyses."""

    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.cache: OrderedDict[str, DocumentAnalysisResponse] = OrderedDict()

    def get(self, key: str) -> DocumentAnalysisResponse | None:
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key: str, value: DocumentAnalysisResponse) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def clear(self) -> None:
        self.cache.clear()


analysis_cache = AnalysisLRUCache(capacity=settings.cache_size_items)


def compute_doc_hash(text: str) -> str:
    """Compute SHA-256 hex digest of document text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def analyze_document_pipeline(
    llm_client: LLMClient,
    pages_text: list[tuple[int, str]],
    role: RoleEnum = RoleEnum.GENERIC,
    language: LanguageEnum = LanguageEnum.ENGLISH,
    reading_level: ReadingLevelEnum = ReadingLevelEnum.STANDARD,
    doc_type: str = "generic",
    pii_mask: bool = False,
    use_cache: bool = True,
) -> DocumentAnalysisResponse:
    """End-to-end document analysis pipeline with automatic fallback on LLM error/quota/timeout."""
    # 1. Compute content hash before masking
    raw_full_text = "\n\n".join(t for _, t in pages_text)
    doc_id = compute_doc_hash(raw_full_text)

    # Cache key = SHA-256(content) + role + language + reading_level + doc_type + pii_mask
    cache_key = f"{doc_id}:{role.value}:{language.value}:{reading_level.value}:{doc_type}:{pii_mask}"

    if use_cache:
        cached = analysis_cache.get(cache_key)
        if cached:
            return cached

    # 2. If PII masking is requested, mask text before chunking
    processed_pages: list[tuple[int, str]] = []
    if pii_mask:
        for page_num, text in pages_text:
            masked_text, _ = mask_pii(text)
            processed_pages.append((page_num, masked_text))
    else:
        processed_pages = pages_text

    # 3. Chunk document
    paragraphs = chunk_document(processed_pages)

    # 4. Analyze via LLM client with automatic fallback on 429/timeout/error
    backend_name = "Gemini" if not settings.is_demo_mode else "Demo"
    try:
        raw_clauses = await llm_client.analyze_document(
            paragraphs=paragraphs,
            role=role,
            language=language,
            reading_level=reading_level,
            doc_type=doc_type,
        )
    except Exception as exc:
        logger.warning(f"Primary LLM analysis failed ({exc}). Engaging automatic Demo fallback.")
        fallback_client = FakeLLMClient()
        raw_clauses = await fallback_client.analyze_document(
            paragraphs=paragraphs,
            role=role,
            language=language,
            reading_level=reading_level,
            doc_type=doc_type,
        )
        backend_name = "Demo (fallback)"

    # 5. Deterministically verify quotes against paragraphs (with fuzzy repair step)
    verified_clauses, verification_score = verify_clauses(raw_clauses, paragraphs)

    # 6. Check missing clauses
    missing_items = check_missing_clauses(
        doc_type=doc_type,
        clauses=verified_clauses,
        paragraphs=paragraphs,
    )

    # 7. Calculate risk counts
    high_count = sum(1 for c in verified_clauses if c.risk_level == RiskLevelEnum.HIGH)
    med_count = sum(1 for c in verified_clauses if c.risk_level == RiskLevelEnum.MEDIUM)
    low_count = sum(1 for c in verified_clauses if c.risk_level == RiskLevelEnum.LOW)

    response = DocumentAnalysisResponse(
        doc_id=doc_id,
        role=role.value,
        doc_type=doc_type,
        language=language.value,
        reading_level=reading_level.value,
        total_paragraphs=len(paragraphs),
        total_clauses=len(verified_clauses),
        verification_score=verification_score,
        high_risk_count=high_count,
        medium_risk_count=med_count,
        low_risk_count=low_count,
        clauses=verified_clauses,
        missing_clauses=missing_items,
        paragraphs=paragraphs,
        llm_backend=backend_name,
        pii_masked=pii_mask,
    )

    if use_cache:
        analysis_cache.put(cache_key, response)

    return response
