"""Sanitization, prompt-injection defense, and optional PII masking."""
import html
import re

# Regex patterns for sensitive PII
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")

# Prompt injection markers to sanitize from untrusted text before LLM insertion
INJECTION_MARKERS = [
    (re.compile(r"<\s*/?\s*contract_text(?:_[ab])?\s*>", re.IGNORECASE), "[ESCAPED_DOC_TAG]"),
    (re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE), "[ESCAPED_SYS_TAG]"),
    (re.compile(r"<<SYS>>|<<\/SYS>>", re.IGNORECASE), "[ESCAPED_SYS_TAG]"),
    (re.compile(r"\[INST\]|\[\/INST\]", re.IGNORECASE), "[ESCAPED_INST]"),
    (re.compile(r"(?i)\b(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|above|prior)\s+(?:instructions|rules|prompts)\b"), "[ATTEMPTED_INSTRUCTION_OVERRIDE_IGNORED]"),
    (re.compile(r"(?i)\byou\s+are\s+now\s+(?:a|an)\b"), "[ATTEMPTED_ROLE_CHANGE_IGNORED]"),
    (re.compile(r"(?i)\b(?:system\s+prompt|system\s+directive|system|new\s+instructions?)\s*:", re.IGNORECASE), "[ATTEMPTED_SYSTEM_DIRECTIVE_IGNORED]:"),
]


def mask_pii(text: str) -> tuple[str, int]:
    """Mask personally identifiable information (emails, phones, SSNs, credit cards).
    
    Returns (masked_text, total_replacements).
    """
    total = 0

    def repl_email(m):
        nonlocal total
        total += 1
        return "[MASKED_EMAIL]"

    def repl_phone(m):
        nonlocal total
        total += 1
        return "[MASKED_PHONE]"

    def repl_ssn(m):
        nonlocal total
        total += 1
        return "[MASKED_SSN]"

    def repl_cc(m):
        nonlocal total
        total += 1
        return "[MASKED_CARD]"

    masked = EMAIL_REGEX.sub(repl_email, text)
    masked = PHONE_REGEX.sub(repl_phone, masked)
    masked = SSN_REGEX.sub(repl_ssn, masked)
    masked = CREDIT_CARD_REGEX.sub(repl_cc, masked)
    return masked, total


def sanitize_untrusted_text(text: str) -> str:
    """Sanitize untrusted text to prevent prompt injection and delimiter breakout."""
    sanitized = text
    for pattern, replacement in INJECTION_MARKERS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def wrap_document_boundary(text: str, tag_name: str = "contract_text") -> str:
    """Safely encapsulate untrusted document text within strict XML delimiters."""
    clean_text = sanitize_untrusted_text(text)
    return f"<{tag_name}>\n{clean_text}\n</{tag_name}>"


def escape_html_safely(text: str) -> str:
    """Standard HTML entity escaping for web rendering."""
    return html.escape(text, quote=True)
