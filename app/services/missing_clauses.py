"""Deterministic missing-clause checklist engine by document type."""
import re
from typing import Any

from app.models.schemas import (
    ClauseAnalysis,
    MissingClauseItem,
    MissingStatusEnum,
    ParagraphChunk,
)

# Standard clause definitions by document type
CHECKLISTS: dict[str, list[dict[str, Any]]] = {
    "rental": [
        {
            "name": "Security Deposit Return & Deductions",
            "category": "Deposit",
            "keywords": [r"\bsecurity deposit\b", r"\bdeposit return\b", r"\bitemized deduction\b"],
            "why_it_matters": "Clarifies return deadlines (typically 14-30 days) and prevents arbitrary deductions for normal wear and tear.",
            "question_to_ask": "What is the exact statutory deadline for returning the security deposit, and will deductions be restricted strictly to tenant negligence rather than ordinary wear and tear?",
        },
        {
            "name": "Landlord Entry Notice Requirement",
            "category": "Privacy",
            "keywords": [r"\b(?:24|48)[\s-]hours?\s+notice\b", r"\breasonable notice\b", r"\bwritten notice before entry\b"],
            "why_it_matters": "Protects tenant right to quiet enjoyment by requiring at least 24 or 48 hours advance notice before landlord enters.",
            "question_to_ask": "Will you add a clause requiring at least 24 hours advance written notice before landlord entry, except in bona fide emergencies?",
        },
        {
            "name": "Maintenance & Habitability Standards",
            "category": "Maintenance",
            "keywords": [r"\bmaintenance and repair\b", r"\bhabitability\b", r"\brepair and maintenance\b", r"\broutine plumbing\b"],
            "why_it_matters": "Defines who pays for major appliance, plumbing, heating, and structural repairs.",
            "question_to_ask": "Can we clarify that the landlord remains fully responsible for maintaining heating, electrical, plumbing, and major appliances without per-incident deductibles?",
        },
        {
            "name": "Rent Increase Notice & Cap",
            "category": "Rent",
            "keywords": [r"\brent increase\b", r"\bnotice of rent increase\b", r"\brent adjustment\b", r"\bcap on rent\b"],
            "why_it_matters": "Protects tenant against sudden, unannounced rent spikes upon lease renewal.",
            "question_to_ask": "What notice period (e.g. 60 or 90 days) is required before any rent increase, and is there a percentage cap on increases upon renewal?",
        },
        {
            "name": "Early Termination & Subletting Terms",
            "category": "Termination",
            "keywords": [r"\bearly termination\b", r"\bliquidated damages\b", r"\bsublet(?:ting)?\b", r"\bassignment\b"],
            "why_it_matters": "Provides a reasonable exit path without catastrophic full-term rent liability if relocation or hardship occurs.",
            "question_to_ask": "Can we include an early lease termination provision permitting lease break with 60 days written notice and a maximum 2-month rent fee?",
        },
    ],
    "freelance": [
        {
            "name": "Payment Schedule, Milestones & Late Fees",
            "category": "Payment",
            "keywords": [r"\bnet[- ](?:15|30)\b", r"\blate fee\b", r"\binterest\b", r"\bcompensation\b", r"\binvoice\b"],
            "why_it_matters": "Ensures prompt compensation and provides financial recourse if client delays invoice payments.",
            "question_to_ask": "Can we specify Net-15 or Net-30 payment terms with 1.5% monthly late interest accruing on overdue invoices?",
        },
        {
            "name": "Scope of Work & Revision Limits",
            "category": "Scope",
            "keywords": [r"\bscope of services\b", r"\brevision(?:s)?\b", r"\bout-of-scope\b", r"\brounds of\b"],
            "why_it_matters": "Prevents 'scope creep' by strictly defining included deliverables and hourly rates for additional revision requests.",
            "question_to_ask": "Does this contract define the exact number of revision rounds included and the agreed hourly rate for subsequent revisions?",
        },
        {
            "name": "IP Ownership Transfer Conditioned on Payment",
            "category": "IP",
            "keywords": [r"\bupon (?:full|final) payment\b", r"\bconditioned on payment\b", r"\bintellectual property\b", r"\bwork product\b"],
            "why_it_matters": "Crucial contractor protection: ensures copyright remains with contractor until client has paid all invoices in full.",
            "question_to_ask": "Can we clarify that copyright and IP transfer to the client occurs strictly upon receipt of full and final payment?",
        },
        {
            "name": "Cancellation & Kill Fee",
            "category": "Termination",
            "keywords": [r"\bkill fee\b", r"\bcancellation fee\b", r"\bterminate without cause\b", r"\bearly cancellation\b"],
            "why_it_matters": "Compensates freelancer for reserved time and opportunity cost if the client abruptly cancels an ongoing project.",
            "question_to_ask": "If the project is terminated early without cause, will client pay a kill fee (e.g. 25-50% of the remaining milestone fees)?",
        },
        {
            "name": "Mutual Limitation of Liability",
            "category": "Liability",
            "keywords": [r"\blimitation of liability\b", r"\baggregate liability\b", r"\bfees paid\b", r"\bconsequential\b"],
            "why_it_matters": "Caps freelancer liability to the actual amount earned under the contract, shielding personal assets.",
            "question_to_ask": "Can we confirm that neither party's aggregate liability shall exceed the total fees paid under this agreement?",
        },
    ],
    "employment": [
        {
            "name": "Compensation, Overtime & Bonus Structure",
            "category": "Compensation",
            "keywords": [r"\bsalary\b", r"\bbase compensation\b", r"\bbonus\b", r"\bovertime\b"],
            "why_it_matters": "Defines base pay, payment intervals, and conditions required to earn incentive bonuses.",
            "question_to_ask": "What are the specific performance criteria, calculation metrics, and vesting dates for discretionary or performance bonuses?",
        },
        {
            "name": "Termination Notice & Severance Terms",
            "category": "Termination",
            "keywords": [r"\bseverance\b", r"\bnotice period\b", r"\btermination without cause\b", r"\bwritten notice\b"],
            "why_it_matters": "Provides financial and temporal runway if employment is ended without cause.",
            "question_to_ask": "In the event of termination without cause, what severance pay or advance notice period is guaranteed?",
        },
        {
            "name": "Non-Compete Scope & Duration",
            "category": "Restrictive Covenants",
            "keywords": [r"\bnon-compete\b", r"\brestrictive covenant\b", r"\bcompeting business\b"],
            "why_it_matters": "Overly broad non-competes can prevent an employee from working in their field after leaving.",
            "question_to_ask": "Are any non-compete restrictions reasonably tailored in geographic scope and limited to a duration under one year?",
        },
        {
            "name": "IP Inventions Assignment Exclusions",
            "category": "IP",
            "keywords": [r"\binventions assignment\b", r"\bprior inventions\b", r"\bcarve-out\b", r"\bown time\b"],
            "why_it_matters": "Ensures side projects developed on personal time without company resources remain the employee's property.",
            "question_to_ask": "Does the agreement include a schedule to list and protect prior inventions and personal side projects?",
        },
    ],
    "nda": [
        {
            "name": "Definition & Scope of Confidential Information",
            "category": "Scope",
            "keywords": [r"\bconfidential information\b", r"\bproprietary\b", r"\btrade secret\b"],
            "why_it_matters": "Prevents ambiguity by clearly defining what materials must be kept confidential.",
            "question_to_ask": "Does the definition require confidential written materials to be explicitly marked as 'Confidential'?",
        },
        {
            "name": "Standard Exclusions from Confidentiality",
            "category": "Exclusions",
            "keywords": [r"\bpublicly known\b", r"\bprior knowledge\b", r"\bindependently developed\b", r"\bexclusions\b"],
            "why_it_matters": "Standard carve-outs protect recipients from liability for information already in the public domain.",
            "question_to_ask": "Are standard exceptions included for publicly known info, court-ordered disclosures, and independently developed concepts?",
        },
        {
            "name": "Definite Term & Duration of Obligation",
            "category": "Term",
            "keywords": [r"\bperiod of\s+\d+\s+years\b", r"\bterm of this agreement\b", r"\bsurvive for\b", r"\bduration\b"],
            "why_it_matters": "Non-disclosure obligations should expire after a reasonable window (e.g. 1 to 3 years) rather than lasting indefinitely.",
            "question_to_ask": "What is the expiration date or finite term for the non-disclosure obligation?",
        },
        {
            "name": "Return or Destruction of Materials",
            "category": "Remedies",
            "keywords": [r"\breturn or destroy\b", r"\bpromptly return\b", r"\bdestruction of\b", r"\bcertification\b"],
            "why_it_matters": "Provides orderly protocol for deleting or returning sensitive materials upon agreement termination.",
            "question_to_ask": "What is the procedure and timeline for returning or certifying the destruction of confidential data?",
        },
    ],
    "generic": [
        {
            "name": "Governing Law and Jurisdiction",
            "category": "Legal",
            "keywords": [r"\bgoverning law\b", r"\bjurisdiction\b", r"\bvenue\b", r"\blaws of\b"],
            "why_it_matters": "Determines which state or country's legal system resolves any dispute.",
            "question_to_ask": "Which jurisdiction and governing law controls this contract, and is the venue convenient for both parties?",
        },
        {
            "name": "Dispute Resolution & Legal Fees",
            "category": "Dispute",
            "keywords": [r"\barbitration\b", r"\bmediation\b", r"\battorney(?:s')?\s+fees\b", r"\bdispute resolution\b"],
            "why_it_matters": "Specifies whether disputes go to court or arbitration, and whether prevailing party recovers legal expenses.",
            "question_to_ask": "Is there a mutual attorney fees clause where the prevailing party recovers costs, rather than a one-sided provision?",
        },
        {
            "name": "Termination & Notice Period",
            "category": "Termination",
            "keywords": [r"\bterminat\w*\b", r"\bwritten notice\b", r"\bexpiration\b"],
            "why_it_matters": "Defines how and when either party can safely end the business relationship.",
            "question_to_ask": "What written notice timeframe is required for termination with or without cause?",
        },
        {
            "name": "Entire Agreement (Integration Clause)",
            "category": "Integration",
            "keywords": [r"\bentire agreement\b", r"\bsupersedes\b", r"\bmerger clause\b", r"\bcomplete understanding\b"],
            "why_it_matters": "Confirms that verbal promises not written in the contract have no legal effect.",
            "question_to_ask": "Have all prior verbal representations or email promises been incorporated into the written contract text?",
        },
    ],
}


def check_missing_clauses(
    doc_type: str,
    clauses: list[ClauseAnalysis],
    paragraphs: list[ParagraphChunk],
) -> list[MissingClauseItem]:
    """Check expected clauses for the document type and report FOUND or NOT_FOUND."""
    dt_key = doc_type.lower()
    if dt_key not in CHECKLISTS:
        dt_key = "generic"

    checklist = CHECKLISTS[dt_key]
    results: list[MissingClauseItem] = []

    for item in checklist:
        name = item["name"]
        cat = item["category"]
        keywords = item["keywords"]
        why = item["why_it_matters"]
        ask = item["question_to_ask"]

        found_pids: list[str] = []
        found_excerpt: str | None = None

        # 1. Search paragraphs for matching regexes
        for p in paragraphs:
            p_text = p.text
            for kw in keywords:
                m = re.search(kw, p_text, re.IGNORECASE)
                if m:
                    if p.paragraph_id not in found_pids:
                        found_pids.append(p.paragraph_id)
                    if not found_excerpt:
                        start = max(0, m.start() - 30)
                        end = min(len(p_text), m.end() + 70)
                        found_excerpt = p_text[start:end].strip()

        # 2. Also search analyzed clauses for category/title overlap
        for c in clauses:
            if cat.lower() in c.category.lower() or name.lower() in c.title.lower():
                for ev in c.evidence:
                    if ev.paragraph_id not in found_pids:
                        found_pids.append(ev.paragraph_id)
                if not found_excerpt and c.evidence:
                    found_excerpt = c.evidence[0].exact_quote

        if found_pids:
            results.append(
                MissingClauseItem(
                    clause_name=name,
                    category=cat,
                    status=MissingStatusEnum.FOUND,
                    why_it_matters=why,
                    question_to_ask=ask,
                    found_in_paragraphs=found_pids,
                    found_quote=found_excerpt,
                )
            )
        else:
            results.append(
                MissingClauseItem(
                    clause_name=name,
                    category=cat,
                    status=MissingStatusEnum.NOT_FOUND,
                    why_it_matters=why,
                    question_to_ask=ask,
                    found_in_paragraphs=[],
                    found_quote=None,
                )
            )

    return results
