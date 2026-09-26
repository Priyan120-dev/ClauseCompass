"""Integration tests for FastAPI REST API endpoints."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security.ratelimit import limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.clear()


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "demo_mode" in data
    assert "backend" in data


def test_samples_endpoint():
    response = client.get("/api/samples")
    assert response.status_code == 200
    data = response.json()
    assert "samples" in data
    assert len(data["samples"]) >= 3


def test_sample_detail_endpoint():
    response = client.get("/api/samples/rental_agreement")
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "Apex Realty Partners" in data["text"]


def test_sample_detail_not_found():
    response = client.get("/api/samples/non_existent_file")
    assert response.status_code == 404


def test_ingest_endpoint_raw_text():
    response = client.post("/api/ingest", data={"raw_text": "Paragraph 1.\n\nParagraph 2."})
    assert response.status_code == 200
    data = response.json()
    assert data["total_paragraphs"] == 2
    assert data["paragraphs"][0]["paragraph_id"] == "p1"


def test_ingest_endpoint_empty_fails():
    response = client.post("/api/ingest", data={})
    assert response.status_code == 400


def test_upload_renamed_fake_pdf_rejected():
    fake_pdf = b"Just plain text disguised with a .pdf extension"
    files = {"file": ("fake_contract.pdf", fake_pdf, "application/pdf")}
    response = client.post("/api/ingest", files=files)
    assert response.status_code == 400
    assert "magic bytes" in response.json()["detail"].lower()


def test_analyze_endpoint_demo_mode():
    with open("samples/rental_agreement.txt", encoding="utf-8") as f:
        sample_text = f.read()

    response = client.post(
        "/api/analyze",
        data={
            "raw_text": sample_text,
            "role": "tenant",
            "doc_type": "rental",
            "language": "en",
            "reading_level": "standard",
            "pii_mask": "false",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["doc_type"] == "rental"
    assert data["role"] == "tenant"
    assert data["total_clauses"] >= 5
    assert data["verification_score"] > 80.0
    assert data["high_risk_count"] >= 3
    assert len(data["missing_clauses"]) > 0


def test_analyze_endpoint_with_pii_masking():
    raw_with_pii = (
        "Apex Realty Partners LLC and Alex Rivera enter this lease.\n"
        "Alex's email is alex@example.com and phone is 555-432-1234.\n\n"
        "Tenant pays monthly rent of $2,400.00 USD on the 1st."
    )
    response = client.post(
        "/api/analyze",
        data={
            "raw_text": raw_with_pii,
            "role": "tenant",
            "doc_type": "rental",
            "pii_mask": "true",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pii_masked"] is True
    # Verify masked text in returned paragraphs
    full_p_text = " ".join(p["text"] for p in data["paragraphs"])
    assert "alex@example.com" not in full_p_text
    assert "[MASKED_EMAIL]" in full_p_text


def test_analyze_stream_sse_endpoint():
    with open("samples/rental_agreement.txt", encoding="utf-8") as f:
        sample_text = f.read()

    response = client.post(
        "/api/analyze/stream",
        data={
            "raw_text": sample_text,
            "role": "tenant",
            "doc_type": "rental",
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    text = response.text
    assert "data: " in text
    assert '"stage": "ingesting"' in text
    assert '"stage": "complete"' in text


def test_qa_endpoint():
    with open("samples/rental_agreement.txt", encoding="utf-8") as f:
        sample_text = f.read()

    response = client.post(
        "/api/qa",
        json={
            "document_text": sample_text,
            "question": "Can the landlord enter without notice?",
            "role": "tenant",
            "language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ANSWERED"
    assert len(data["citations"]) > 0
    assert data["citations"][0]["verification_status"] == "VERIFIED"


def test_qa_endpoint_unmentioned():
    with open("samples/rental_agreement.txt", encoding="utf-8") as f:
        sample_text = f.read()

    response = client.post(
        "/api/qa",
        json={
            "document_text": sample_text,
            "question": "Are pets like dogs or cats allowed?",
            "role": "tenant",
            "language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "NOT_DETERMINABLE"
    assert "cannot be determined from this document" in data["answer"].lower()


def test_compare_endpoint():
    with open("samples/freelance_v1.txt", encoding="utf-8") as f:
        doc_a = f.read()
    with open("samples/freelance_v2.txt", encoding="utf-8") as f:
        doc_b = f.read()

    response = client.post(
        "/api/compare",
        json={
            "doc_a_text": doc_a,
            "doc_b_text": doc_b,
            "role": "freelancer",
            "language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_differences"] >= 3
    assert len(data["items"]) >= 3


def test_export_ics_endpoint():
    with open("samples/rental_agreement.txt", encoding="utf-8") as f:
        sample_text = f.read()

    analysis_res = client.post(
        "/api/analyze",
        data={"raw_text": sample_text, "role": "tenant", "doc_type": "rental"},
    )
    analysis_data = analysis_res.json()

    ics_res = client.post("/api/export/ics", json=analysis_data)
    assert ics_res.status_code == 200
    assert "BEGIN:VCALENDAR" in ics_res.text
    assert "BEGIN:VEVENT" in ics_res.text
    assert "END:VCALENDAR" in ics_res.text


def test_export_brief_endpoint():
    with open("samples/rental_agreement.txt", encoding="utf-8") as f:
        sample_text = f.read()

    analysis_res = client.post(
        "/api/analyze",
        data={"raw_text": sample_text, "role": "tenant", "doc_type": "rental"},
    )
    analysis_data = analysis_res.json()

    brief_res = client.post("/api/export/brief", json=analysis_data)
    assert brief_res.status_code == 200
    assert "# Legal Review Brief" in brief_res.text
    assert "Questions for Your Lawyer" in brief_res.text


def test_export_markdown_endpoint():
    with open("samples/rental_agreement.txt", encoding="utf-8") as f:
        sample_text = f.read()

    analysis_res = client.post(
        "/api/analyze",
        data={"raw_text": sample_text, "role": "tenant", "doc_type": "rental"},
    )
    analysis_data = analysis_res.json()

    md_res = client.post("/api/export/markdown", json=analysis_data)
    assert md_res.status_code == 200
    assert "# ClauseCompass Analysis Report" in md_res.text
    assert "Grounded Evidence Citations" in md_res.text


def test_rate_limiter_exceeded():
    limiter.clear()
    headers = {"X-Forwarded-For": "203.0.113.195"}

    # Simulate rapid requests exceeding limit
    for _ in range(60):
        client.get("/api/health", headers=headers)

    # 61st request should trigger 429
    blocked_res = client.get("/api/health", headers=headers)
    assert blocked_res.status_code == 429
    assert "Rate limit exceeded" in blocked_res.json()["detail"]
    assert "Retry-After" in blocked_res.headers
