"""Pydantic data models and schemas for ClauseCompass."""
from enum import Enum

from pydantic import BaseModel, Field


class RoleEnum(str, Enum):
    TENANT = "tenant"
    LANDLORD = "landlord"
    FREELANCER = "freelancer"
    CLIENT = "client"
    EMPLOYEE = "employee"
    EMPLOYER = "employer"
    BUYER = "buyer"
    SELLER = "seller"
    GENERIC = "generic"


class LanguageEnum(str, Enum):
    ENGLISH = "en"
    TAMIL = "ta"
    HINDI = "hi"


class ReadingLevelEnum(str, Enum):
    SIMPLE = "simple"
    STANDARD = "standard"


class RiskLevelEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VerificationStatusEnum(str, Enum):
    VERIFIED = "VERIFIED"
    ALTERED_QUOTE = "ALTERED_QUOTE"
    PARAGRAPH_NOT_FOUND = "PARAGRAPH_NOT_FOUND"
    UNVERIFIED = "UNVERIFIED"


class MissingStatusEnum(str, Enum):
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"


class QAStatusEnum(str, Enum):
    ANSWERED = "ANSWERED"
    PARTIAL = "PARTIAL"
    NOT_DETERMINABLE = "NOT_DETERMINABLE"


class DiffTypeEnum(str, Enum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    UNCHANGED = "UNCHANGED"


class RiskDeltaEnum(str, Enum):
    INCREASED = "increased"
    DECREASED = "decreased"
    NEUTRAL = "neutral"


class ParagraphChunk(BaseModel):
    paragraph_id: str = Field(..., description="Stable identifier, e.g. p1, p2, p1-1")
    page_num: int = Field(default=1, description="1-indexed page number")
    text: str = Field(..., description="Exact paragraph text content")
    token_count: int = Field(default=0, description="Approximate token count")


class EvidenceQuote(BaseModel):
    paragraph_id: str = Field(..., description="Referenced paragraph ID")
    exact_quote: str = Field(..., description="Verbatim quote from the paragraph")
    verification_status: VerificationStatusEnum = Field(
        default=VerificationStatusEnum.UNVERIFIED,
        description="Deterministic verification status"
    )
    verification_details: str | None = Field(
        default=None,
        description="Diagnostic details if quote verification failed or required normalization"
    )


class Obligation(BaseModel):
    who: str = Field(..., description="Party with the duty or responsibility")
    what: str = Field(..., description="Action, payment, or behavior required")
    deadline: str | None = Field(default=None, description="Explicit due date or timeframe")


class ClauseAnalysis(BaseModel):
    clause_id: str = Field(..., description="Unique ID for the clause analysis")
    category: str = Field(..., description="Clause category, e.g. Payment, Termination, Liability")
    title: str = Field(..., description="Short descriptive title for the clause")
    plain_language_summary: str = Field(..., description="Clear summary in requested language and reading level")
    risk_level: RiskLevelEnum = Field(..., description="Risk assessment for user's selected role")
    risk_reason: str = Field(..., description="Specific explanation of why this risk level was assigned")
    user_role_impact: str = Field(..., description="Impact specifically analyzed for the user's role")
    obligations: list[Obligation] = Field(default_factory=list, description="Extracted obligations and deadlines")
    evidence: list[EvidenceQuote] = Field(default_factory=list, description="Grounding evidence quotes and paragraph IDs")
    actionable_recommendation: str | None = Field(
        default=None,
        description="Practical recommendation or question to ask"
    )


class MissingClauseItem(BaseModel):
    clause_name: str = Field(..., description="Standard clause expected in this agreement type")
    category: str = Field(..., description="Functional category")
    status: MissingStatusEnum = Field(..., description="FOUND in document or NOT_FOUND")
    why_it_matters: str = Field(..., description="Why a reasonable party should care about this clause")
    question_to_ask: str = Field(..., description="Specific question to pose to counter-party or attorney")
    found_in_paragraphs: list[str] = Field(default_factory=list, description="Paragraph IDs where detected if found")
    found_quote: str | None = Field(default=None, description="Supporting excerpt if found")


class DocumentAnalysisResponse(BaseModel):
    doc_id: str = Field(..., description="SHA-256 hash or unique ID of the document")
    role: str = Field(..., description="Role chosen by user")
    doc_type: str = Field(..., description="Document type, e.g. rental, freelance, employment, nda, generic")
    language: str = Field(..., description="Language code")
    reading_level: str = Field(..., description="simple or standard")
    total_paragraphs: int
    total_clauses: int
    verification_score: float = Field(..., description="Percentage of citations verified (0-100)")
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    clauses: list[ClauseAnalysis]
    missing_clauses: list[MissingClauseItem]
    paragraphs: list[ParagraphChunk]
    llm_backend: str = Field(default="gemini", description="gemini or demo/fake")
    pii_masked: bool = Field(default=False, description="True if PII masking was applied")


class QARequest(BaseModel):
    doc_id: str | None = None
    document_text: str | None = None
    paragraphs: list[ParagraphChunk] | None = None
    question: str = Field(..., min_length=2, max_length=1000)
    role: RoleEnum = RoleEnum.GENERIC
    language: LanguageEnum = LanguageEnum.ENGLISH


class QAResponse(BaseModel):
    question: str
    answer: str
    status: QAStatusEnum
    citations: list[EvidenceQuote]
    whats_missing_or_to_ask: str | None = None


class CompareRequest(BaseModel):
    doc_a_text: str = Field(..., min_length=10)
    doc_b_text: str = Field(..., min_length=10)
    role: RoleEnum = RoleEnum.GENERIC
    language: LanguageEnum = LanguageEnum.ENGLISH
    doc_a_name: str | None = "Document A (Original)"
    doc_b_name: str | None = "Document B (Revised)"


class ClauseComparisonItem(BaseModel):
    category: str
    title: str
    diff_type: DiffTypeEnum
    doc_a_summary: str | None = None
    doc_b_summary: str | None = None
    doc_a_evidence: list[EvidenceQuote] = Field(default_factory=list)
    doc_b_evidence: list[EvidenceQuote] = Field(default_factory=list)
    who_benefits: str = Field(..., description="Party gaining advantage from change")
    risk_delta: RiskDeltaEnum = Field(..., description="Risk change for user's role")
    explanation: str = Field(..., description="Plain-language explanation of difference")


class CompareResponse(BaseModel):
    doc_a_name: str
    doc_b_name: str
    total_differences: int
    items: list[ClauseComparisonItem]
    overall_summary: str
