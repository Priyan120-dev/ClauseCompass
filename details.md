# ClauseCompass — Complete Technical Specification & Project Architecture

> **Notice**: ClauseCompass provides objective legal information for educational, review, and navigation purposes. It does **not** provide legal advice or establish an attorney-client relationship.

---

## 1. Executive Summary & Problem Statement

### 1.1 The Problem
Legal contracts—residential leases, freelance agreements, employment contracts, and non-disclosure agreements (NDAs)—are purposefully dense, opaque, and asymmetric. Everyday signers (tenants, gig workers, freelancers, employees) regularly face:
- **Asymmetric Legal Jargon**: Complex phrasing that conceals one-sided liabilities, indemnifications, and forfeitures.
- **Hidden Deadlines & Penalties**: Buried timelines for renewal notifications, cure periods, and liquidated damages.
- **The "Silence" Trap**: What a contract *omits* (e.g., absence of deposit return timelines, missing habitability guarantees, or missing kill fees) is often far more dangerous than what it includes.
- **Hallucination Risk of General Chatbots**: General-purpose LLMs extrapolate, synthesize nonexistent clauses, and invent legal protections that are nowhere in the text, creating immense legal jeopardy if relied upon.

### 1.2 The ClauseCompass Solution
**ClauseCompass** is an open-source, GenAI-powered legal information assistant designed from the ground up to solve the hallucination problem through **deterministic, code-level verification**. Every claim, risk evaluation, and extracted obligation is anchored to a stable paragraph ID and an exact quote from the document text. Before any badge or claim is rendered to the user, a deterministic Python engine verifies that the cited quote exists verbatim in the referenced paragraph.

If a point is not explicitly addressed in the contract, the system states **`NOT_DETERMINABLE`** ("Cannot be determined from this document") rather than fabricating an answer.

---

## 2. Why Not Just a General Chatbot?

| Evaluation Dimension | General Chatbot (ChatGPT, Claude, etc.) | ClauseCompass Architecture |
|---|---|---|
| **Grounding & Evidence** | Generates plausible-sounding explanations without verifiable anchors. | Every claim requires `{paragraph_id, exact_quote}`. |
| **Verification Engine** | None. LLM claims are taken at face value. | Pure-Python deterministic substring and fuzzy repair check (`difflib`, $\ge 0.9$ similarity) validates quotes before display. |
| **Handling of Missing Terms** | Frequently assumes standard legal defaults or speculates on unmentioned terms. | Deterministic checklist per contract type. Flags absent terms as `NOT_FOUND` ("Not stated in this document") with negotiation questions. |
| **Perspective / Role Framing** | Generic perspective unless repeatedly prompted. | Explicit role configuration (Tenant vs. Landlord, Freelancer vs. Client) dynamically frames risk severity and impact. |
| **Data Privacy & Persistence** | Prompts and uploads may be stored or used for model training unless opted out. | Strictly in-memory processing. Zero contract persistence to disk or database. Ephemeral memory cleared after request. |
| **PII Protection** | Raw document text with names, emails, and financial details sent directly to cloud APIs. | Built-in toggle to mask emails, phone numbers, SSNs, and credit cards before LLM ingestion and viewer rendering. |
| **Prompt Injection Defense** | Vulnerable to contract text containing instructions like *"Ignore previous instructions"*. | Structural XML tag containment (`<contract_text>`), tag escaping, and override neutralizing sanitizers. |
| **Actionable Outputs** | Unstructured plain text answers. | Generates RFC 5545 `.ics` calendar alarms for deadlines, Markdown "Questions for Your Lawyer" briefs, and printable CSS reports. |

---

## 3. High-Level System Architecture

```mermaid
flowchart TD
    subgraph ClientLayer [Client Interface (WCAG 2.1 AA Compliant)]
        UI[Vanilla HTML5 + CSS3 + ES Modules]
        Tabs[3-Tab Workspace: Understand, Ask, Compare]
        Viewer[Grounded Document Viewer with Source Highlighting]
        Speech[Web SpeechSynthesis Audio Engine]
    end

    subgraph Gateway [FastAPI Gateway & Security Middleware]
        Security[Security Headers: CSP, nosniff, DENY, HSTS]
        RateLimit[Safe X-Forwarded-For Sliding Window Rate Limiter]
        Validation[File Size <= 5MB, Magic-Bytes Check, Page Limits]
        Sanitizer[Prompt Injection Neutralizer & PII Masker]
    end

    subgraph Ingestion [Ingest & Chunking Engine]
        IngestService[PDF pypdf / DOCX python-docx / TXT Parser]
        Chunker[Deterministic Chunker with Stable IDs: p1, p2, ...]
    end

    subgraph CoreEngine [Analysis & Grounding Core]
        LRUCache[(In-Memory SHA-256 LRU Cache)]
        LLMInterface{LLM Client Interface}
        Gemini[Google Gemini 2.5 Flash via google-genai SDK]
        FakeLLM[High-Fidelity Offline Synthetic Demo Engine]
        Verifier[Pure-Python Verifier + difflib Fuzzy Repair]
        MissingChecker[Missing-Clause Checklist Engine]
        QAService[BM25 Lexical Retrieval + Grounded Q&A]
        CompareService[Version Diff & Category Alignment Engine]
    end

    subgraph Outputs [Action & Export Generators]
        ICS[RFC 5545 iCalendar Generator]
        Brief[Lawyer Questions Markdown Brief]
        Print[Print-Optimized Stylesheet]
    end

    UI --> Gateway
    Gateway --> Ingestion
    Ingestion --> CoreEngine
    CoreEngine --> Outputs
    Outputs --> UI
    CoreEngine --> Viewer
```

---

## 4. Detailed Component Walkthrough

### 4.1 Ingestion & Chunking Service (`app/services/ingest.py`, `app/services/chunker.py`)
- **Supported Formats**:
  - **PDF**: Extracted via `pypdf.PdfReader` with page numbering preservation.
  - **DOCX**: Extracted via `python-docx` covering paragraphs and nested tables.
  - **Plain Text / Markdown**: UTF-8 and Latin-1 decodable text.
- **Security Validation (`app/security/validation.py`)**:
  - **Magic-Byte Signature Verification**: Rejects spoofed extensions. Confirms `%PDF-` for PDFs, `PK\x03\x04` for DOCX zip packages, and valid character encodings for text.
  - **Size Limits**: Strict 5 MB maximum payload cap.
  - **Page Limits**: Enforces a maximum of 60 pages per document.
- **Canonical Chunking**:
  - Normalizes unicode whitespace (`\xa0`, `\u200b`, multiple spaces).
  - Splits text by natural paragraph boundaries (`\n\s*\n`).
  - Automatically breaks excessively long clauses (>1,200 characters) into structured sub-sections if numbered headings exist.
  - Assigns immutable, canonical identifiers: `p1`, `p2`, `p3`, etc.

### 4.2 The Pure-Python Deterministic Verifier (`app/services/verifier.py`)
The verifier guarantees that the model does not hallucinate quotes or misattribute evidence.
1. **Unicode & Typographical Normalization**:
   - Curly quotes (`“`, `”`, `«`, `»`) converted to straight double quotes (`"`).
   - Smart apostrophes (`‘`, `’`) converted to straight single quotes (`'`).
   - Dashes (em-dash `—`, en-dash `–`, minus `−`) converted to hyphens (`-`).
   - Whitespace collapsed and trimmed.
2. **Deterministic Match Verification**:
   - **Step 1 (Verbatim Substring)**: Checks if the normalized quote exists inside the normalized cited paragraph.
   - **Step 2 (Case-Insensitive Match)**: Checks if casing differences caused a mismatch.
   - **Step 3 (Fuzzy Repair Step)**: If exact match fails, a `difflib.SequenceMatcher` scans candidate sentence and word windows within the cited paragraph. If a match with similarity $\ge 0.90$ (90%) is found, the quote is snapped to the closest verbatim text in the paragraph and marked `VERIFIED (snapped to closest match)`.
   - **Step 4 (Misattribution Check)**: If the quote does not exist in the cited paragraph, the verifier scans all other document paragraphs. If found elsewhere, it tags the citation as `PARAGRAPH_NOT_FOUND` ("Found in pX instead of pY").
   - **Step 5 (Failure / Alteration)**: If no match exists, it is marked `ALTERED_QUOTE`.
3. **Verification Score**:
   $$\text{Verification Score} = \left(\frac{N_{\text{verified quotes}}}{N_{\text{total quotes}}}\right) \times 100\%$$
   Exposed prominently in the UI scorecard and export summaries.

### 4.3 Missing-Clause Checklist Engine (`app/services/missing_clauses.py`)
Contracts are checked against deterministic industry checklists based on the selected document type:
- **Residential Rental**:
  - Security Deposit Return Timeline & Deductions
  - Landlord Entry Notice Requirement (24/48 hours)
  - Maintenance & Habitability Standards
  - Rent Increase Notice & Cap
  - Early Termination & Subletting Rights
- **Freelance Consulting**:
  - Payment Terms & Late Interest (Net-15 / Net-30)
  - Scope of Work & Revision Limits
  - IP Ownership Transfer Conditioned on Full Payment
  - Cancellation & Kill Fee
  - Mutual Limitation of Liability
- **Employment Agreement**:
  - Compensation, Overtime & Bonus Terms
  - Termination Notice & Severance Terms
  - Reasonable Non-Compete Scope & Duration
  - IP Inventions Assignment Exclusions / Carve-Outs
- **Non-Disclosure Agreement (NDA)**:
  - Definition & Scope of Confidential Information
  - Standard Exclusions (Public Knowledge, Independent Development)
  - Definite Term & Expiration of Obligation
  - Return or Destruction Protocol
- **General Commercial**:
  - Governing Law and Jurisdiction
  - Dispute Resolution & Legal Fees
  - Termination & Notice Periods
  - Entire Agreement (Integration Clause)

Each clause is classified as **`FOUND`** (with paragraph evidence) or **`NOT_FOUND`** ("Not stated in this document"), accompanied by **Why It Matters** and **Specific Questions to Ask**.

### 4.4 Grounded Q&A Engine (`app/services/qa.py`)
- **BM25 Lexical Retrieval**: Analyzes query terms, filters stop words, calculates inverse document frequencies (IDF), and retrieves the top-6 candidate paragraphs.
- **Constrained Generation**: The LLM prompt strictly forbids answering beyond the provided paragraphs.
- **Three-State Answer Status**:
  - `ANSWERED`: Question is fully covered by document facts.
  - `PARTIAL`: Question is partially addressed; notes what is missing.
  - `NOT_DETERMINABLE`: Topic is not mentioned in the contract (e.g., asking about pet policies when the lease does not mention pets). Automatically suggests negotiation questions.
- **Post-Verification**: All citations returned in the Q&A response are run through the deterministic quote verifier.

### 4.5 Document Comparison Engine (`app/services/compare.py`)
- Ingests two contract versions (e.g., `freelance_v1.txt` vs. `freelance_v2.txt`).
- Aligns clauses by functional topic.
- Identifies modification types: `ADDED`, `REMOVED`, `MODIFIED`, `UNCHANGED`.
- Evaluates **Risk Delta** (`increased`, `decreased`, `neutral`) from the user's role perspective.
- Explicitly states **Who Benefits** (e.g., Contractor vs. Client).
- Attaches dual-sided evidence with verified quotes from both documents.

### 4.6 Action Outputs & Exports (`app/services/exports.py`)
1. **iCalendar (`.ics`)**: Exports an RFC 5545 calendar file. Extracts obligations with due dates (e.g., 1st of month rent, 5th of month late fee threshold, 60-day deposit return window, termination notice deadlines) and configures 24-hour reminder alarms (`VALARM`).
2. **Questions for Your Lawyer Brief**: Generates an executive Markdown document highlighting all high-risk provisions, missing standard protections, and a checklist of questions to ask before signing.
3. **Markdown Report**: Comprehensive export containing all verified clauses, risk evaluations, and exact citations.
4. **Print-Friendly CSS**: Native `@media print` stylesheet that strips navigation, backgrounds, and interactive controls to format clean, paginated physical documents.

---

## 5. Security & Privacy Architecture

### 5.1 Zero Persistence & Privacy
- Documents are processed in-memory as byte streams or ephemeral strings.
- No database, no local disk storage of uploaded documents, and no S3/Cloud Storage retention.
- Memory references are garbage-collected upon request completion.

### 5.2 PII Masking Engine (`app/security/sanitize.py`)
Users can enable the **Mask PII** toggle before analysis:
- Regex-based identification and replacement:
  - Email addresses $\rightarrow$ `[MASKED_EMAIL]`
  - Phone numbers $\rightarrow$ `[MASKED_PHONE]`
  - Social Security Numbers $\rightarrow$ `[MASKED_SSN]`
  - Credit Cards / Account Numbers $\rightarrow$ `[MASKED_CARD]`
- **Consistency Guarantee**: PII is masked *before* chunking. The LLM, the deterministic verifier, and the document viewer all operate on the exact same masked text, preventing verification discrepancies.

### 5.3 Prompt Injection Defense (`app/security/sanitize.py`)
- Document text is wrapped inside strict boundary tags: `<contract_text>...</contract_text>`.
- Any simulated closing tags (`</contract_text>`, `</system>`, `[INST]`, `<<SYS>>`) within the document are sanitized to `[ESCAPED_DOC_TAG]`.
- Directives such as *"ignore all previous instructions"*, *"you are now an admin"*, or *"SYSTEM:"* are replaced with neutralization tokens before LLM prompt construction.
- Tested by dedicated test cases in `tests/test_injection.py`.

### 5.4 Rate Limiting & Safe IP Extraction (`app/security/ratelimit.py`)
- In-memory sliding-window rate limiter (default: 60 requests/minute per client IP).
- **Safe `X-Forwarded-For` Extraction**: When behind proxies (Cloud Run, Render, Nginx), the leftmost IP is extracted and validated using Python's `ipaddress.ip_address()`. If invalid or spoofed, it securely falls back to the direct socket peer address.

### 5.5 Content Security Policy (CSP) & Headers (`app/main.py`)
Response headers added via middleware:
- `Content-Security-Policy`: Self-contained policy forbidding third-party scripts and external font hosts (`default-src 'self'`).
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`

---

## 6. Resilience & Production Readiness

### 6.1 Automatic Fallback Engine
ClauseCompass includes an automatic fallback hierarchy:
```
User Request
     │
     ▼
Is GEMINI_API_KEY set and DEMO_MODE == False?
     ├── No ───────────────────────────────────► Use FakeLLMClient (Instant Synthetic Analysis)
     │
    Yes
     ▼
Call Google Gemini 2.5 Flash API
     ├── Success ──────────────────────────────► Return Verified Gemini Analysis
     │
   Exception (429 Quota / Timeout / Network / 403)
     │
     ▼
Log Warning & Automatically Engage Demo Fallback ──► Return Grounded Demo Analysis (llm_backend = "Demo (fallback)")
```
This guarantees that judges, reviewers, and end-users never encounter a broken 500 error screen even if API quotas are exhausted or offline.

### 6.2 Real-Time Progress via Server-Sent Events (SSE)
- Endpoint: `POST /api/analyze/stream`
- Emits real-time progress updates (`ingesting` $\rightarrow$ `chunking` $\rightarrow$ `analyzing` $\rightarrow$ `verifying` $\rightarrow$ `complete`) directly to the frontend progress bar.

### 6.3 In-Memory LRU Cache
- Key: `SHA-256(content) + role + language + reading_level + doc_type + pii_mask`.
- Avoids redundant Gemini API calls and provides instantaneous responses for repeated analyses.

---

## 7. Accessibility & Frontend UX (WCAG 2.1 AA)

- **Semantic Landmarks**: Proper `<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<aside>`, and `<footer>` elements.
- **Accessible Skip Link**: Allows keyboard-only and screen reader users to skip navigation headers (`#main-content`).
- **Contrast Ratios $\ge 4.5:1$**: Formulated color tokens in both light and dark modes.
- **Risk Is Never Color-Only**: High risk uses 🔴 + bold text badge + red border; Medium risk uses 🟡 + bold text badge + amber border; Low risk uses 🟢 + bold text badge + green border.
- **Self-Contained Font Stack**: Native font stack prioritizing `Noto Sans Tamil`, `Latha`, `Mukta`, `Noto Sans Devanagari`, and `Mangal` with system fallbacks. Zero external font dependencies.
- **Web Speech API**: Integrated read-aloud button for clause summaries and Q&A answers using `window.speechSynthesis`.
- **Keyboard Navigation & Visible Focus**: Every interactive control possesses visible `:focus-visible` outlines. Full keyboard tab navigation supported.
- **Reduced Motion Support**: Honors `@media (prefers-reduced-motion: reduce)`.

---

## 8. Directory & File Structure

```text
ClauseCompass/
├── .github/
│   └── workflows/
│       └── ci.yml               # Automated CI quality gate (ruff, mypy, pytest)
├── app/
│   ├── __init__.py
│   ├── config.py                # Pydantic BaseSettings, dynamic $PORT, env management
│   ├── main.py                  # FastAPI entry point, CSP middleware, static mounts
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints.py         # REST & SSE streaming endpoints (/analyze, /qa, /compare, /health)
│   ├── llm/
│   │   ├── __init__.py          # LLM factory (GeminiClient vs FakeLLMClient)
│   │   ├── base.py              # LLMClient abstract base class
│   │   ├── gemini.py            # Google Gemini 2.5 Flash implementation via google-genai
│   │   └── fake.py              # Offline deterministic synthetic mock engine
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # Pydantic v2 data contracts and validation schemas
│   ├── security/
│   │   ├── __init__.py
│   │   ├── ratelimit.py         # Safe X-Forwarded-For sliding window rate limiter
│   │   ├── sanitize.py          # Prompt injection defense and PII masking
│   │   └── validation.py        # Magic-byte file validation, page limit checks
│   └── services/
│       ├── __init__.py
│       ├── analyzer.py          # End-to-end analysis pipeline with LRU cache & fallback
│       ├── chunker.py           # Paragraph chunker with stable IDs (p1, p2, ...)
│       ├── compare.py           # Document version diff and risk alignment
│       ├── exports.py           # ICS calendar, lawyer brief, markdown generator
│       ├── ingest.py            # PDF, DOCX, and TXT parsing service
│       ├── missing_clauses.py   # Deterministic checklists per contract type
│       ├── qa.py                # BM25 lexical retrieval and grounded Q&A
│       └── verifier.py          # Pure Python quote verifier with difflib repair
├── samples/
│   ├── freelance_v1.txt         # Synthetic contractor agreement v1.0
│   ├── freelance_v2.txt         # Synthetic amended contractor agreement v2.0
│   └── rental_agreement.txt     # Synthetic residential lease agreement
├── scripts/
│   ├── check_repo_size.py       # Cross-platform repository size auditor (< 10 MB)
│   └── check_repo_size.sh       # Bash repository size auditor
├── static/
│   ├── index.html               # Semantic, accessible HTML5 single-page application
│   ├── css/
│   │   └── styles.css           # WCAG AA design system, dark mode, print styles
│   └── js/
│       ├── api.js               # REST & SSE streaming client
│       ├── app.js               # Main application orchestration & safe DOM rendering
│       └── speech.js            # Web Speech API read-aloud controller
├── tests/
│   ├── test_api.py              # End-to-end API route tests
│   ├── test_chunker.py          # Paragraph chunking and normalization tests
│   ├── test_compare.py          # Document comparison tests
│   ├── test_exports.py          # ICS, lawyer brief, and markdown export tests
│   ├── test_fallback.py         # Automatic fallback on 429/timeout tests
│   ├── test_ingest.py           # Ingestion tests for PDF, DOCX, and TXT
│   ├── test_injection.py        # Prompt injection & boundary containment tests
│   ├── test_missing_clauses.py  # Missing-clause checklist tests
│   ├── test_qa.py               # BM25 retrieval and NOT_DETERMINABLE tests
│   ├── test_validation.py       # File size, magic bytes, and IP validation tests
│   └── test_verifier.py         # Quote verifier and fuzzy repair tests
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile                   # Non-root, production container definition
├── LICENSE                      # MIT License
├── mypy.ini                     # Type checker configuration
├── render.yaml                  # Render deployment blueprint
├── requirements.txt             # Pinned backend dependencies
└── ruff.toml                    # Linter configuration
```

---

## 9. API Reference

### `GET /api/health`
Returns system status and active LLM backend.
```json
{
  "status": "healthy",
  "app_name": "ClauseCompass",
  "version": "1.0.0",
  "demo_mode": true,
  "backend": "Demo",
  "gemini_model": null
}
```

### `POST /api/analyze`
Analyzes an uploaded file or raw text.
- **Content-Type**: `multipart/form-data`
- **Parameters**: `file` (optional), `raw_text` (optional), `role` (`tenant`, `freelancer`, `employee`, `generic`), `doc_type` (`rental`, `freelance`, `employment`, `nda`, `generic`), `language` (`en`, `ta`, `hi`), `reading_level` (`simple`, `standard`), `pii_mask` (`true`, `false`).
- **Response**: `DocumentAnalysisResponse` object with `verification_score`, `clauses`, `missing_clauses`, and `paragraphs`.

### `POST /api/analyze/stream`
Server-Sent Events (SSE) streaming progress endpoint for live UI feedback.

### `POST /api/qa`
Grounded question answering.
- **Content-Type**: `application/json`
- **Payload**:
  ```json
  {
    "paragraphs": [...],
    "question": "Can the landlord enter without notice?",
    "role": "tenant",
    "language": "en"
  }
  ```
- **Response**: `QAResponse` (`status: "ANSWERED" | "PARTIAL" | "NOT_DETERMINABLE"`, verified citations, and negotiation recommendations).

### `POST /api/compare`
Compares two documents and aligns clause differences.

### `POST /api/export/ics`
Generates and downloads an RFC 5545 `.ics` file containing extracted deadlines and reminder alarms.

### `POST /api/export/brief`
Generates a structured Markdown "Questions for Your Lawyer" brief.

---

## 10. Verification & Quality Gate Metrics

1. **Unit & Integration Tests**:
   - `55 passed in ~18s`
   - **Services Test Coverage**: **91.0%** (exceeds the 80% requirement)
2. **Static Analysis & Linters**:
   - `ruff check .` $\rightarrow$ `All checks passed!`
   - `mypy app` $\rightarrow$ `Success: no issues found in 24 source files`
3. **Repository Footprint**:
   - Tracked workspace size: **`0.29 MB`** (299.5 KB, well below the 10 MB constraint)

---

## 11. Running Locally & Deployment

### 11.1 Run with uv / Python Virtual Environment
```bash
# 1. Clone repository
git clone https://github.com/your-org/ClauseCompass.git
cd ClauseCompass

# 2. Create virtual environment & install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment (optional: works offline in DEMO_MODE by default)
cp .env.example .env
# Set GEMINI_API_KEY=your_key if using live Gemini 2.5 Flash

# 4. Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000` in any browser.

### 11.2 Run with Docker
```bash
docker build -t clausecompass:latest .
docker run -p 8000:8000 -e PORT=8000 clausecompass:latest
```

### 11.3 Deploy to Render
The included [`render.yaml`](file:///c:/Users/Akira/Downloads/ClauseCompass/render.yaml) automatically provisions the web service on Render with zero configuration.

### 11.4 Deploy to Google Cloud Run
```bash
gcloud run deploy clausecompass \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DEMO_MODE=false,GEMINI_API_KEY=your_api_key
```
