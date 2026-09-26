"""Fake / Mock LLM Client for offline evaluation, testing, and DEMO_MODE."""
import re

from app.llm.base import LLMClient
from app.models.schemas import (
    ClauseAnalysis,
    ClauseComparisonItem,
    CompareResponse,
    DiffTypeEnum,
    EvidenceQuote,
    LanguageEnum,
    Obligation,
    ParagraphChunk,
    QAResponse,
    QAStatusEnum,
    ReadingLevelEnum,
    RiskDeltaEnum,
    RiskLevelEnum,
    RoleEnum,
    VerificationStatusEnum,
)


class FakeLLMClient(LLMClient):
    """High-fidelity mock LLM client providing deterministic, grounded outputs."""

    def __init__(self):
        pass

    async def analyze_document(
        self,
        paragraphs: list[ParagraphChunk],
        role: RoleEnum = RoleEnum.GENERIC,
        language: LanguageEnum = LanguageEnum.ENGLISH,
        reading_level: ReadingLevelEnum = ReadingLevelEnum.STANDARD,
        doc_type: str = "generic",
    ) -> list[ClauseAnalysis]:
        """Analyze clauses from paragraphs."""
        doc_text = " ".join(p.text for p in paragraphs).lower()

        # Check if this matches our synthetic rental agreement
        if "apex realty partners" in doc_text or "742 evergreen terrace" in doc_text:
            return self._analyze_rental_agreement(paragraphs, role, language, reading_level)

        # Check if this matches freelance agreement v1 or v2
        if "novatech solutions" in doc_text and "jordan lee" in doc_text:
            if "version 2.0" in doc_text or "net-15" in doc_text or "kill fee" in doc_text:
                return self._analyze_freelance_v2(paragraphs, role, language, reading_level)
            return self._analyze_freelance_v1(paragraphs, role, language, reading_level)

        # General heuristic analyzer for arbitrary text in demo mode
        return self._heuristic_analyze(paragraphs, role, language, reading_level)

    def _find_para_quote(self, paragraphs: list[ParagraphChunk], keyword_sub: str) -> EvidenceQuote | None:
        """Locate paragraph containing keyword_sub and return EvidenceQuote."""
        for p in paragraphs:
            if keyword_sub.lower() in p.text.lower():
                # Extract the sentence or segment
                sentences = re.split(r"(?<=[.!?])\s+", p.text)
                for s in sentences:
                    if keyword_sub.lower() in s.lower():
                        return EvidenceQuote(
                            paragraph_id=p.paragraph_id,
                            exact_quote=s.strip(),
                            verification_status=VerificationStatusEnum.UNVERIFIED,
                        )
                # Fallback to entire paragraph or first 120 chars
                return EvidenceQuote(
                    paragraph_id=p.paragraph_id,
                    exact_quote=p.text.strip(),
                    verification_status=VerificationStatusEnum.UNVERIFIED,
                )
        return None

    def _analyze_rental_agreement(
        self,
        paragraphs: list[ParagraphChunk],
        role: RoleEnum,
        language: LanguageEnum,
        reading_level: ReadingLevelEnum,
    ) -> list[ClauseAnalysis]:
        is_tenant = (role in (RoleEnum.TENANT, RoleEnum.GENERIC))
        clauses = []

        # 1. Term & Premises
        q1 = self._find_para_quote(paragraphs, "October 1, 2024")
        if q1:
            clauses.append(
                ClauseAnalysis(
                    clause_id="clause-1",
                    category="Term & Premises",
                    title="Lease Term (12 Months)",
                    plain_language_summary=(
                        "The lease runs for exactly 12 months, from Oct 1, 2024 to Sept 30, 2025. You must leave when it ends unless renewed."
                        if reading_level == ReadingLevelEnum.SIMPLE
                        else "Fixed one-year term commencing October 1, 2024 and terminating September 30, 2025 with surrender obligation."
                    ),
                    risk_level=RiskLevelEnum.LOW,
                    risk_reason="Standard fixed-term duration with clearly defined start and end dates.",
                    user_role_impact="Provides secure tenancy for one year with mandatory move-out upon expiration.",
                    obligations=[
                        Obligation(who="Tenant", what="Surrender possession upon termination", deadline="September 30, 2025")
                    ],
                    evidence=[q1],
                    actionable_recommendation="Confirm renewal notice requirements at least 60 days before September 30, 2025.",
                )
            )

        # 2. Rent & Late Fees
        q2 = self._find_para_quote(paragraphs, "ten percent (10%)")
        if q2:
            clauses.append(
                ClauseAnalysis(
                    clause_id="clause-2",
                    category="Payment Terms",
                    title="Rent and 10% Late Fee Penalty",
                    plain_language_summary=(
                        "Rent is $2,400 due on the 1st of each month. If paid after the 5th, a high 10% fee ($240) applies immediately."
                        if reading_level == ReadingLevelEnum.SIMPLE
                        else "Monthly rent of $2,400.00 USD due on the 1st; 10% late fee charged immediately after 11:59 PM on the 5th."
                    ),
                    risk_level=RiskLevelEnum.HIGH if is_tenant else RiskLevelEnum.LOW,
                    risk_reason="A 10% late fee ($240) is unusually high compared to typical residential standards (commonly 3-5%).",
                    user_role_impact="Missing the 5-day grace period results in a steep financial surcharge.",
                    obligations=[
                        Obligation(who="Tenant", what="Pay monthly rent of $2,400.00 USD", deadline="1st day of each month"),
                        Obligation(who="Tenant", what="Pay 10% late fee if unpaid by the 5th", deadline="5th day of month, 11:59 PM"),
                    ],
                    evidence=[q2],
                    actionable_recommendation="Set up automated electronic bank transfer by the 1st to prevent triggering the $240 late charge.",
                )
            )

        # 3. Security Deposit
        q3 = self._find_para_quote(paragraphs, "normal wear and tear")
        if q3:
            clauses.append(
                ClauseAnalysis(
                    clause_id="clause-3",
                    category="Security Deposit",
                    title="Deposit Return & Deductions for Wear and Tear",
                    plain_language_summary=(
                        "Deposit is 2 months rent ($4,800). The landlord gives themselves 60 days to return it and claims they can deduct for normal wear and tear."
                        if reading_level == ReadingLevelEnum.SIMPLE
                        else "$4,800 deposit with 60-day return window. Authorizes deductions for ordinary wear and tear, which contradicts tenant-protective standards."
                    ),
                    risk_level=RiskLevelEnum.HIGH if is_tenant else RiskLevelEnum.LOW,
                    risk_reason="Deducting for 'normal wear and tear' is legally improper in many jurisdictions, and 60 days is an unusually long return window.",
                    user_role_impact="High risk of losing part or all of the $4,800 deposit for customary apartment usage.",
                    obligations=[
                        Obligation(who="Tenant", what="Pay $4,800.00 security deposit", deadline="Upon execution"),
                        Obligation(who="Landlord", what="Return remaining deposit with itemized deductions", deadline="Within 60 days of surrender"),
                    ],
                    evidence=[q3],
                    actionable_recommendation="Take thorough move-in photos and ask landlord to remove 'normal wear and tear' deduction wording.",
                )
            )

        # 4. Maintenance & Repairs Under $500
        q4 = self._find_para_quote(paragraphs, "$500.00 USD")
        if q4:
            clauses.append(
                ClauseAnalysis(
                    clause_id="clause-4",
                    category="Maintenance & Repairs",
                    title="Tenant Liable for Repairs Under $500",
                    plain_language_summary=(
                        "You must pay out of pocket for any repair costing under $500, including appliances and plumbing."
                        if reading_level == ReadingLevelEnum.SIMPLE
                        else "Tenant bears full financial liability for all maintenance and appliance repairs under $500 per incident."
                    ),
                    risk_level=RiskLevelEnum.HIGH if is_tenant else RiskLevelEnum.LOW,
                    risk_reason="Shifts standard landlord habitability obligations onto the tenant for major appliances and plumbing.",
                    user_role_impact="Tenant may incur frequent unexpected repair bills for aging landlord appliances.",
                    obligations=[
                        Obligation(who="Tenant", what="Maintain premises and pay for repairs under $500", deadline="Per incident"),
                        Obligation(who="Landlord", what="Repair structural defects and exterior roofing", deadline="Upon written notice"),
                    ],
                    evidence=[q4],
                    actionable_recommendation="Request clause amendment so tenant is only responsible for damage caused by tenant negligence.",
                )
            )

        # 5. Landlord Entry Without Notice
        q5 = self._find_para_quote(paragraphs, "without prior written notice")
        if q5:
            clauses.append(
                ClauseAnalysis(
                    clause_id="clause-5",
                    category="Privacy & Access",
                    title="Unannounced Landlord Entry",
                    plain_language_summary=(
                        "The landlord claims they can enter your home at any time of day or night without giving you any advance notice."
                        if reading_level == ReadingLevelEnum.SIMPLE
                        else "Clause permits landlord unrestricted access at any hour without prior written notice."
                    ),
                    risk_level=RiskLevelEnum.HIGH if is_tenant else RiskLevelEnum.LOW,
                    risk_reason="Severe privacy infringement; standard leases require at least 24 or 48 hours advance written notice for non-emergencies.",
                    user_role_impact="Loss of quiet enjoyment and unannounced intrusions into personal living space.",
                    obligations=[
                        Obligation(who="Landlord", what="May enter premises to inspect or show unit", deadline="Any time without notice"),
                    ],
                    evidence=[q5],
                    actionable_recommendation="Insist on inserting: 'Landlord must provide at least 24 hours advance written notice except in bona fide emergencies.'",
                )
            )

        # 6. Early Termination Penalty
        q6 = self._find_para_quote(paragraphs, "liquidated damages")
        if q6:
            clauses.append(
                ClauseAnalysis(
                    clause_id="clause-6",
                    category="Termination & Penalties",
                    title="Full Term Rent Liability Plus $3,000 Liquidated Damages",
                    plain_language_summary=(
                        "If you need to move out early, you still owe all rent through the end of the year, forfeit your $4,800 deposit, and must pay a $3,000 penalty."
                        if reading_level == ReadingLevelEnum.SIMPLE
                        else "Early lease termination requires full rent acceleration through end of term, deposit forfeiture, and a $3,000.00 fee."
                    ),
                    risk_level=RiskLevelEnum.HIGH if is_tenant else RiskLevelEnum.LOW,
                    risk_reason="Excessive punitive damages that ignore landlord's legal duty to mitigate damages by re-renting.",
                    user_role_impact="Catastrophic financial liability if job relocation or emergency forces early move.",
                    obligations=[
                        Obligation(who="Tenant", what="Pay remaining rent balance and $3,000 liquidated damages fee", deadline="Within 7 days of vacancy"),
                    ],
                    evidence=[q6],
                    actionable_recommendation="Negotiate a standard early termination fee (e.g. 2 months rent with 60 days written notice).",
                )
            )

        # 7. Asymmetric Legal Fees
        q7 = self._find_para_quote(paragraphs, "attorney fees")
        if q7:
            clauses.append(
                ClauseAnalysis(
                    clause_id="clause-7",
                    category="Dispute Resolution",
                    title="One-Sided Attorney Fees and Jury Waiver",
                    plain_language_summary=(
                        "If there is a lawsuit and the landlord wins, you pay their lawyer fees. But if you win, the landlord never pays your lawyer fees."
                        if reading_level == ReadingLevelEnum.SIMPLE
                        else "Asymmetrical attorney fee provision paired with mandatory arbitration and jury waiver."
                    ),
                    risk_level=RiskLevelEnum.HIGH if is_tenant else RiskLevelEnum.LOW,
                    risk_reason="One-sided legal fee recovery disincentivizes tenant from asserting legitimate legal rights.",
                    user_role_impact="Tenant risks paying landlord legal bills without reciprocal protection if landlord breaches lease.",
                    obligations=[
                        Obligation(who="Tenant", what="Reimburse landlord attorney fees if landlord prevails", deadline="Upon dispute judgment"),
                    ],
                    evidence=[q7],
                    actionable_recommendation="Request mutual attorney fees clause: 'The prevailing party in any action shall be entitled to reasonable attorney fees.'",
                )
            )

        return clauses

    def _analyze_freelance_v1(
        self,
        paragraphs: list[ParagraphChunk],
        role: RoleEnum,
        language: LanguageEnum,
        reading_level: ReadingLevelEnum,
    ) -> list[ClauseAnalysis]:
        is_freelancer = (role in (RoleEnum.FREELANCER, RoleEnum.GENERIC))
        clauses = []

        q1 = self._find_para_quote(paragraphs, "$120.00 USD")
        if q1:
            clauses.append(
                ClauseAnalysis(
                    clause_id="fl1-comp",
                    category="Compensation & Payment",
                    title="Hourly Rate ($120/hr) with Net-30 Payment",
                    plain_language_summary="Contractor is paid $120/hour for up to 80 hours per month. Invoices are paid on Net-30 terms.",
                    risk_level=RiskLevelEnum.MEDIUM if is_freelancer else RiskLevelEnum.LOW,
                    risk_reason="Net-30 payment delay means waiting up to 30 days after invoice submission without late interest provisions.",
                    user_role_impact="Cash flow delay; contractor carries financing risk for 30+ days.",
                    obligations=[
                        Obligation(who="Contractor", what="Invoice client bi-weekly for up to 80 hours", deadline="Bi-weekly"),
                        Obligation(who="Client", what="Pay approved invoices", deadline="Within 30 calendar days (Net-30)"),
                    ],
                    evidence=[q1],
                    actionable_recommendation="Request Net-15 payment terms and a 1.5% monthly late payment fee.",
                )
            )

        q2 = self._find_para_quote(paragraphs, "regardless of whether full payment")
        if q2:
            clauses.append(
                ClauseAnalysis(
                    clause_id="fl1-ip",
                    category="Intellectual Property",
                    title="Immediate IP Transfer Prior to Payment",
                    plain_language_summary="All work product and copyright ownership transfers to Client immediately upon creation, even if Client never pays you.",
                    risk_level=RiskLevelEnum.HIGH if is_freelancer else RiskLevelEnum.LOW,
                    risk_reason="Contractor loses all leverage if Client defaults on payment, as Client already owns the intellectual property.",
                    user_role_impact="Extreme risk of unpaid work where client retains full copyright and commercial rights.",
                    obligations=[
                        Obligation(who="Contractor", what="Assigns all worldwide copyright and patent rights to Client upon creation", deadline="Immediate"),
                    ],
                    evidence=[q2],
                    actionable_recommendation="Change transfer condition: IP ownership transfers strictly upon receipt of full and final payment.",
                )
            )

        q3 = self._find_para_quote(paragraphs, "fourteen (14) calendar days")
        if q3:
            clauses.append(
                ClauseAnalysis(
                    clause_id="fl1-term",
                    category="Termination",
                    title="14-Day Termination Without Kill Fee",
                    plain_language_summary="Either party can cancel the agreement with 14 days notice. Client only pays for hours completed with no cancellation compensation.",
                    risk_level=RiskLevelEnum.MEDIUM if is_freelancer else RiskLevelEnum.LOW,
                    risk_reason="Short notice period with zero kill fee or minimum commitment protects client more than contractor.",
                    user_role_impact="Client can abandon project midway with only 14 days notice.",
                    obligations=[
                        Obligation(who="Either Party", what="Provide written termination notice", deadline="14 calendar days notice"),
                    ],
                    evidence=[q3],
                    actionable_recommendation="Add a 25% kill fee or 30-day notice requirement for termination without cause.",
                )
            )

        return clauses

    def _analyze_freelance_v2(
        self,
        paragraphs: list[ParagraphChunk],
        role: RoleEnum,
        language: LanguageEnum,
        reading_level: ReadingLevelEnum,
    ) -> list[ClauseAnalysis]:
        is_freelancer = (role in (RoleEnum.FREELANCER, RoleEnum.GENERIC))
        clauses = []

        q1 = self._find_para_quote(paragraphs, "Net-15")
        if q1:
            clauses.append(
                ClauseAnalysis(
                    clause_id="fl2-comp",
                    category="Compensation & Payment",
                    title="Net-15 Payment Terms with 1.5% Late Interest",
                    plain_language_summary="Client must pay invoices within 15 days, with 1.5% monthly late interest accruing on overdue amounts.",
                    risk_level=RiskLevelEnum.LOW if is_freelancer else RiskLevelEnum.MEDIUM,
                    risk_reason="Favorable payment terms protecting contractor cash flow with enforceable late fee deterrence.",
                    user_role_impact="Prompt payment expectation with contractual protection against delayed payments.",
                    obligations=[
                        Obligation(who="Client", what="Pay approved invoices", deadline="Within 15 calendar days (Net-15)"),
                        Obligation(who="Client", what="Pay 1.5% monthly late interest on overdue balances", deadline="Upon overdue status"),
                    ],
                    evidence=[q1],
                    actionable_recommendation="Maintain prompt invoicing on scheduled bi-weekly dates.",
                )
            )

        q2 = self._find_para_quote(paragraphs, "full and final payment")
        if q2:
            clauses.append(
                ClauseAnalysis(
                    clause_id="fl2-ip",
                    category="Intellectual Property",
                    title="Conditional IP Transfer Upon Full Payment",
                    plain_language_summary="IP remains Contractor's property until Client has made full and final payment for all invoices.",
                    risk_level=RiskLevelEnum.LOW if is_freelancer else RiskLevelEnum.MEDIUM,
                    risk_reason="Standard protective clause ensuring contractor retains copyright until fully compensated.",
                    user_role_impact="Preserves contractor leverage in the event of non-payment or disputed fees.",
                    obligations=[
                        Obligation(who="Contractor", what="Assigns copyright and patent rights to Client", deadline="Upon verified payment in full"),
                    ],
                    evidence=[q2],
                    actionable_recommendation="Ensure final payment is confirmed in bank before releasing raw design files or source repositories.",
                )
            )

        q3 = self._find_para_quote(paragraphs, "twenty-five percent (25%)")
        if q3:
            clauses.append(
                ClauseAnalysis(
                    clause_id="fl2-term",
                    category="Termination & Kill Fee",
                    title="30-Day Notice and 25% Cancellation Fee",
                    plain_language_summary="Cancellation requires 30 days notice. If Client cancels without cause, Client must pay a 25% kill fee on remaining project fees.",
                    risk_level=RiskLevelEnum.LOW if is_freelancer else RiskLevelEnum.MEDIUM,
                    risk_reason="Provides substantial buffer and income guarantee against abrupt project cancellation.",
                    user_role_impact="Secures predictable revenue even if client changes direction.",
                    obligations=[
                        Obligation(who="Either Party", what="Provide written termination notice", deadline="30 calendar days notice"),
                        Obligation(who="Client", what="Pay 25% cancellation fee if terminating without cause", deadline="Upon termination"),
                    ],
                    evidence=[q3],
                    actionable_recommendation="Document project milestone budget clearly in Schedule A to easily calculate the 25% figure.",
                )
            )

        q4 = self._find_para_quote(paragraphs, "NON-SOLICITATION")
        if q4:
            clauses.append(
                ClauseAnalysis(
                    clause_id="fl2-nonsol",
                    category="Restrictive Covenants",
                    title="Client Non-Solicitation of Contractor Staff",
                    plain_language_summary="Client is prohibited from hiring or poaching Contractor's team members or subcontractors for 12 months.",
                    risk_level=RiskLevelEnum.LOW if is_freelancer else RiskLevelEnum.HIGH,
                    risk_reason="Protects contractor's talent and team relationships from client poaching.",
                    user_role_impact="Safeguards contractor's business and subcontractor network.",
                    obligations=[
                        Obligation(who="Client", what="Refrain from soliciting Contractor employees or contractors", deadline="During term and 12 months thereafter"),
                    ],
                    evidence=[q4],
                    actionable_recommendation="Ensure subcontractors also have reciprocal non-circumvention agreements.",
                )
            )

        return clauses

    def _heuristic_analyze(
        self,
        paragraphs: list[ParagraphChunk],
        role: RoleEnum,
        language: LanguageEnum,
        reading_level: ReadingLevelEnum,
    ) -> list[ClauseAnalysis]:
        """Fallback rule-based analyzer for arbitrary uploaded documents in demo mode."""
        clauses = []
        clause_idx = 1

        for p in paragraphs:
            text = p.text.strip()
            if len(text) < 40:
                continue

            lower_text = text.lower()
            category = "General Terms"
            risk = RiskLevelEnum.LOW
            title = f"Clause {clause_idx}"
            reason = "Standard contractual clause."
            recommendation = "Review clause details carefully."

            if any(w in lower_text for w in ["rent", "payment", "fee", "compensation", "invoic", "cost", "dollar", "$"]):
                category = "Payment & Fees"
                title = "Payment and Financial Obligations"
                if any(w in lower_text for w in ["late fee", "penalty", "interest", "deduct", "forfeit"]):
                    risk = RiskLevelEnum.HIGH
                    reason = "Contains penalty or forfeiture terms affecting payments."
                    recommendation = "Verify due dates, grace periods, and late penalty calculations."
                else:
                    risk = RiskLevelEnum.MEDIUM
                    reason = "Defines ongoing financial obligations and invoicing schedules."
            elif any(w in lower_text for w in ["terminat", "cancel", "expire", "vacat", "notice"]):
                category = "Termination & Notice"
                title = "Termination and Cancellation Rights"
                if any(w in lower_text for w in ["immediate", "forfeit", "damages", "without cause", "sole discretion"]):
                    risk = RiskLevelEnum.HIGH
                    reason = "Allows abrupt cancellation or imposes damages upon termination."
                    recommendation = "Ensure adequate notice periods (30+ days) and reasonable exit terms."
                else:
                    risk = RiskLevelEnum.MEDIUM
                    reason = "Outlines termination requirements and notice periods."
            elif any(w in lower_text for w in ["liab", "indemn", "hold harmless", "damage", "warrant"]):
                category = "Liability & Indemnity"
                title = "Liability and Risk Allocation"
                risk = RiskLevelEnum.HIGH
                reason = "Allocates legal and financial liability between the parties."
                recommendation = "Seek reciprocal limitation of liability capped at fees paid."
            elif any(w in lower_text for w in ["intellectual property", "copyright", "patent", "work made for hire", "work product"]):
                category = "Intellectual Property"
                title = "Intellectual Property Ownership"
                risk = RiskLevelEnum.HIGH
                reason = "Determines ownership of created works, software, or creative materials."
                recommendation = "Verify whether IP transfer is conditioned on receipt of full payment."
            elif any(w in lower_text for w in ["confidential", "non-disclosure", "trade secret", "proprietary"]):
                category = "Confidentiality"
                title = "Confidentiality & Non-Disclosure"
                risk = RiskLevelEnum.MEDIUM
                reason = "Imposes secrecy obligations and restrictions on information sharing."
                recommendation = "Check duration of confidentiality and ensure reasonable carve-outs."
            elif any(w in lower_text for w in ["deposit", "security"]):
                category = "Security Deposit"
                title = "Security Deposit and Returns"
                risk = RiskLevelEnum.HIGH
                reason = "Governs holding, deduction, and return of deposited funds."
                recommendation = "Ensure return window is 30 days or less with itemized accounting required."

            first_sentence = re.split(r"(?<=[.!?])\s+", text)[0].strip()
            if len(first_sentence) > 180:
                first_sentence = first_sentence[:180] + "..."

            clauses.append(
                ClauseAnalysis(
                    clause_id=f"clause-{clause_idx}",
                    category=category,
                    title=title,
                    plain_language_summary=f"This section governs {category.lower()}: {first_sentence}",
                    risk_level=risk,
                    risk_reason=reason,
                    user_role_impact=f"Relevant impact for your role ({role.value}) under {category.lower()} guidelines.",
                    obligations=[
                        Obligation(who="Party", what=first_sentence[:100], deadline="As specified")
                    ],
                    evidence=[
                        EvidenceQuote(
                            paragraph_id=p.paragraph_id,
                            exact_quote=first_sentence,
                            verification_status=VerificationStatusEnum.UNVERIFIED,
                        )
                    ],
                    actionable_recommendation=recommendation,
                )
            )
            clause_idx += 1
            if clause_idx > 8:
                break

        return clauses

    async def answer_question(
        self,
        paragraphs: list[ParagraphChunk],
        question: str,
        role: RoleEnum = RoleEnum.GENERIC,
        language: LanguageEnum = LanguageEnum.ENGLISH,
    ) -> QAResponse:
        """Answer question with grounding status and citations."""
        q_lower = question.lower()
        full_doc = " ".join(p.text for p in paragraphs).lower()

        # Check for unmentioned topics (e.g. pets in rental agreement, smoking, parking)
        unmentioned_topics = ["pet", "dog", "cat", "smoking", "marijuana", "parking", "sub-lease fee", "gym"]
        for topic in unmentioned_topics:
            if topic in q_lower and topic not in full_doc:
                return QAResponse(
                    question=question,
                    answer=f"This agreement contains no provision regarding {topic}s or related rules. Cannot be determined from this document.",
                    status=QAStatusEnum.NOT_DETERMINABLE,
                    citations=[],
                    whats_missing_or_to_ask=f"Ask the other party or landlord in writing: 'What is the specific policy and fee schedule regarding {topic}s?'",
                )

        # Rental specific queries
        if "access" in q_lower or "enter" in q_lower or "notice" in q_lower and "entry" in q_lower:
            for p in paragraphs:
                if "enter the premises" in p.text.lower() or "without prior written notice" in p.text.lower():
                    quote = "Landlord and Landlord's authorized agents, contractors, and prospective buyers or mortgagees may enter the Premises at any time of day or night without prior written notice"
                    if quote.lower() not in p.text.lower():
                        quote = p.text[:120]
                    return QAResponse(
                        question=question,
                        answer="According to Section 5, the landlord may enter the apartment at any time of day or night without providing prior written notice.",
                        status=QAStatusEnum.ANSWERED,
                        citations=[
                            EvidenceQuote(
                                paragraph_id=p.paragraph_id,
                                exact_quote=quote,
                                verification_status=VerificationStatusEnum.UNVERIFIED,
                            )
                        ],
                        whats_missing_or_to_ask="Request an amendment requiring at least 24 hours advance written notice except in genuine emergencies.",
                    )

        if "deposit" in q_lower or "wear and tear" in q_lower or "return" in q_lower and "deposit" in q_lower:
            for p in paragraphs:
                if "security deposit" in p.text.lower():
                    quote = "Landlord shall return the remaining balance within sixty (60) days following full surrender of the Premises, accompanied by an itemized deduction statement."
                    if quote.lower() not in p.text.lower():
                        quote = p.text[:120]
                    return QAResponse(
                        question=question,
                        answer="The tenant must deposit $4,800. The landlord has up to 60 days after move-out to return the balance and claims deductions for normal wear and tear.",
                        status=QAStatusEnum.ANSWERED,
                        citations=[
                            EvidenceQuote(
                                paragraph_id=p.paragraph_id,
                                exact_quote=quote,
                                verification_status=VerificationStatusEnum.UNVERIFIED,
                            )
                        ],
                        whats_missing_or_to_ask="Ask to strike 'normal wear and tear' from deductible items and reduce the return timeframe to 14-30 days.",
                    )

        if "terminate" in q_lower or "early" in q_lower or "break" in q_lower and "lease" in q_lower:
            for p in paragraphs:
                if "liquidated damages" in p.text.lower() or "vacates, abandons" in p.text.lower():
                    quote = "Tenant shall remain strictly liable for the entire rent balance remaining through September 30, 2025. In addition, Tenant shall forfeit the full security deposit and pay a liquidated damages cancellation penalty of $3,000.00 USD within seven (7) days of vacancy."
                    if quote.lower() not in p.text.lower():
                        quote = p.text[:120]
                    return QAResponse(
                        question=question,
                        answer="Breaking the lease early makes you liable for the entire remaining rent through September 30, 2025, forfeits your $4,800 deposit, and incurs an extra $3,000 penalty fee.",
                        status=QAStatusEnum.ANSWERED,
                        citations=[
                            EvidenceQuote(
                                paragraph_id=p.paragraph_id,
                                exact_quote=quote,
                                verification_status=VerificationStatusEnum.UNVERIFIED,
                            )
                        ],
                        whats_missing_or_to_ask="Ask for a standard early termination clause allowing lease break with 60 days notice and a 1-2 month rent fee.",
                    )

        # Keyword search matching for general questions
        words = [w for w in re.findall(r"\w+", q_lower) if len(w) > 3]
        best_p: ParagraphChunk | None = None
        best_matches = 0
        for p in paragraphs:
            matches = sum(1 for w in words if w in p.text.lower())
            if matches > best_matches:
                best_matches = matches
                best_p = p

        if best_p and best_matches >= 1:
            first_sentence = re.split(r"(?<=[.!?])\s+", best_p.text)[0].strip()
            return QAResponse(
                question=question,
                answer=f"Based on paragraph {best_p.paragraph_id}: {first_sentence}",
                status=QAStatusEnum.PARTIAL,
                citations=[
                    EvidenceQuote(
                        paragraph_id=best_p.paragraph_id,
                        exact_quote=first_sentence,
                        verification_status=VerificationStatusEnum.UNVERIFIED,
                    )
                ],
                whats_missing_or_to_ask="Review full section or ask counter-party for clarification on this point.",
            )

        return QAResponse(
            question=question,
            answer="This specific question cannot be determined from the provided document text.",
            status=QAStatusEnum.NOT_DETERMINABLE,
            citations=[],
            whats_missing_or_to_ask="Ask the drafting party or consult legal counsel to define this term explicitly.",
        )

    async def compare_documents(
        self,
        paragraphs_a: list[ParagraphChunk],
        paragraphs_b: list[ParagraphChunk],
        role: RoleEnum = RoleEnum.GENERIC,
        language: LanguageEnum = LanguageEnum.ENGLISH,
        doc_a_name: str = "Document A (Original)",
        doc_b_name: str = "Document B (Revised)",
    ) -> CompareResponse:
        """Compare two documents with aligned categories and diff types."""
        text_a = " ".join(p.text for p in paragraphs_a).lower()
        text_b = " ".join(p.text for p in paragraphs_b).lower()

        # If comparing freelance v1 vs v2
        if "novatech" in text_a and "novatech" in text_b:
            items = [
                ClauseComparisonItem(
                    category="Payment Terms",
                    title="Payment Terms & Late Interest",
                    diff_type=DiffTypeEnum.MODIFIED,
                    doc_a_summary="Net-30 payment terms without late interest provisions.",
                    doc_b_summary="Net-15 payment terms with 1.5% monthly late interest on overdue invoices.",
                    doc_a_evidence=[
                        EvidenceQuote(
                            paragraph_id="p2",
                            exact_quote="Client shall pay all approved invoices within thirty (30) calendar days of invoice receipt (\"Net-30\").",
                        )
                    ],
                    doc_b_evidence=[
                        EvidenceQuote(
                            paragraph_id="p2",
                            exact_quote="Client shall pay all approved invoices within fifteen (15) calendar days of invoice receipt (\"Net-15\"). Any late payments shall accrue interest at the rate of 1.5% per month or the maximum rate permitted by law.",
                        )
                    ],
                    who_benefits="Contractor / Freelancer",
                    risk_delta=RiskDeltaEnum.DECREASED,
                    explanation="Shortens payment window by 15 days and adds late fee protection against delayed payments.",
                ),
                ClauseComparisonItem(
                    category="Intellectual Property",
                    title="Timing of IP Transfer",
                    diff_type=DiffTypeEnum.MODIFIED,
                    doc_a_summary="IP transferred immediately upon creation, even if contractor has not been paid.",
                    doc_b_summary="IP remains contractor property until client delivers full and final payment.",
                    doc_a_evidence=[
                        EvidenceQuote(
                            paragraph_id="p4",
                            exact_quote="shall become the immediate and exclusive property of Client upon creation, as a work made for hire, regardless of whether full payment for said services has been received by Contractor.",
                        )
                    ],
                    doc_b_evidence=[
                        EvidenceQuote(
                            paragraph_id="p4",
                            exact_quote="shall remain the intellectual property of Contractor until Client has delivered full and final payment for all outstanding invoices.",
                        )
                    ],
                    who_benefits="Contractor / Freelancer",
                    risk_delta=RiskDeltaEnum.DECREASED,
                    explanation="Major improvement for contractor: prevents client from seizing code without paying.",
                ),
                ClauseComparisonItem(
                    category="Termination & Kill Fee",
                    title="Notice Period & Early Cancellation Fee",
                    diff_type=DiffTypeEnum.MODIFIED,
                    doc_a_summary="14 days notice, zero kill fee.",
                    doc_b_summary="30 days notice plus 25% kill fee on remaining project budget if client cancels without cause.",
                    doc_a_evidence=[
                        EvidenceQuote(
                            paragraph_id="p7",
                            exact_quote="Either party may terminate this Agreement without cause upon providing fourteen (14) calendar days written notice.",
                        )
                    ],
                    doc_b_evidence=[
                        EvidenceQuote(
                            paragraph_id="p7",
                            exact_quote="Either party may terminate this Agreement without cause upon providing thirty (30) calendar days written notice. In the event of termination by Client without cause, Client shall pay Contractor for all hours worked to date plus a cancellation fee equal to twenty-five percent (25%) of the remaining scheduled project fees.",
                        )
                    ],
                    who_benefits="Contractor / Freelancer",
                    risk_delta=RiskDeltaEnum.DECREASED,
                    explanation="Provides financial safety net and extended transition period if project is cancelled.",
                ),
                ClauseComparisonItem(
                    category="Non-Solicitation",
                    title="Non-Solicitation Covenant",
                    diff_type=DiffTypeEnum.ADDED,
                    doc_a_summary=None,
                    doc_b_summary="Client barred from soliciting Contractor's staff or subcontractors for 12 months.",
                    doc_a_evidence=[],
                    doc_b_evidence=[
                        EvidenceQuote(
                            paragraph_id="p9",
                            exact_quote="Client agrees not to directly or indirectly solicit, recruit, or hire any employees, contractors, or subcontractors of Contractor without prior written consent.",
                        )
                    ],
                    who_benefits="Contractor / Freelancer",
                    risk_delta=RiskDeltaEnum.DECREASED,
                    explanation="New protective covenant preventing client from poaching contractor's team.",
                ),
            ]
            return CompareResponse(
                doc_a_name=doc_a_name,
                doc_b_name=doc_b_name,
                total_differences=len(items),
                items=items,
                overall_summary="Document B (Version 2.0) significantly favors the Contractor with Net-15 payment, conditional IP transfer upon full payment, a 25% kill fee, and staff non-solicitation.",
            )

        # Fallback comparison heuristic for arbitrary documents
        items = [
            ClauseComparisonItem(
                category="General Agreement Scope",
                title="Clause Alignment & Content Review",
                diff_type=DiffTypeEnum.MODIFIED if len(paragraphs_a) != len(paragraphs_b) else DiffTypeEnum.UNCHANGED,
                doc_a_summary=f"{len(paragraphs_a)} paragraphs analyzed in original version.",
                doc_b_summary=f"{len(paragraphs_b)} paragraphs analyzed in revised version.",
                doc_a_evidence=[
                    EvidenceQuote(
                        paragraph_id=paragraphs_a[0].paragraph_id if paragraphs_a else "p1",
                        exact_quote=paragraphs_a[0].text[:100] if paragraphs_a else "",
                    )
                ] if paragraphs_a else [],
                doc_b_evidence=[
                    EvidenceQuote(
                        paragraph_id=paragraphs_b[0].paragraph_id if paragraphs_b else "p1",
                        exact_quote=paragraphs_b[0].text[:100] if paragraphs_b else "",
                    )
                ] if paragraphs_b else [],
                who_benefits="Neutral / Mutual",
                risk_delta=RiskDeltaEnum.NEUTRAL,
                explanation="Structural comparison between Document A and Document B.",
            )
        ]
        return CompareResponse(
            doc_a_name=doc_a_name,
            doc_b_name=doc_b_name,
            total_differences=len(items),
            items=items,
            overall_summary="Comparison completed between both document versions.",
        )
