"""FastAPI REST API routes and SSE streaming progress endpoints."""
import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.config import settings
from app.llm import get_llm_client
from app.models.schemas import (
    CompareRequest,
    CompareResponse,
    DocumentAnalysisResponse,
    LanguageEnum,
    QARequest,
    QAResponse,
    ReadingLevelEnum,
    RoleEnum,
)
from app.security.ratelimit import rate_limit_dependency
from app.services.analyzer import analyze_document_pipeline
from app.services.chunker import chunk_document
from app.services.compare import execute_compare
from app.services.exports import generate_ics_calendar, generate_lawyer_brief, generate_markdown_export
from app.services.ingest import extract_text_from_bytes, extract_text_from_raw_string
from app.services.qa import execute_grounded_qa

router = APIRouter(prefix="/api", dependencies=[Depends(rate_limit_dependency)])
SAMPLES_DIR = Path("samples")


@router.get("/health")
async def health_check():
    """Health check endpoint indicating active LLM backend and demo mode status."""
    backend_name = "Demo" if settings.is_demo_mode else "Gemini"
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "demo_mode": settings.is_demo_mode,
        "backend": backend_name,
        "gemini_model": settings.gemini_model if not settings.is_demo_mode else None,
    }


@router.get("/samples")
async def list_sample_documents():
    """List bundled synthetic sample contracts."""
    samples = []
    if SAMPLES_DIR.exists():
        for f in SAMPLES_DIR.glob("*.txt"):
            samples.append({
                "id": f.stem,
                "filename": f.name,
                "title": f.stem.replace("_", " ").title(),
            })
    return {"samples": samples}


@router.get("/samples/{sample_id}")
async def get_sample_document(sample_id: str):
    """Retrieve text content of a bundled synthetic sample."""
    path = SAMPLES_DIR / f"{sample_id}.txt"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample '{sample_id}' not found.",
        )
    return {"id": sample_id, "text": path.read_text(encoding="utf-8")}


@router.post("/ingest")
async def ingest_document(
    file: UploadFile | None = File(None),
    raw_text: str | None = Form(None),
):
    """Ingest document from uploaded file or pasted string and return stable chunks."""
    if file:
        content = await file.read()
        pages = await asyncio.to_thread(extract_text_from_bytes, file.filename or "uploaded.txt", content)
    elif raw_text and raw_text.strip():
        pages = extract_text_from_raw_string(raw_text)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a valid file or raw text must be provided.",
        )

    paragraphs = chunk_document(pages)
    return {
        "total_paragraphs": len(paragraphs),
        "paragraphs": paragraphs,
    }


@router.post("/analyze", response_model=DocumentAnalysisResponse)
async def analyze_document_endpoint(
    file: UploadFile | None = File(None),
    raw_text: str | None = Form(None),
    role: RoleEnum = Form(RoleEnum.GENERIC),
    language: LanguageEnum = Form(LanguageEnum.ENGLISH),
    reading_level: ReadingLevelEnum = Form(ReadingLevelEnum.STANDARD),
    doc_type: str = Form("generic"),
    pii_mask: bool = Form(False),
):
    """Analyze a legal contract, verify quotes, and detect missing clauses."""
    if file:
        content = await file.read()
        pages = await asyncio.to_thread(extract_text_from_bytes, file.filename or "uploaded.txt", content)
    elif raw_text and raw_text.strip():
        pages = extract_text_from_raw_string(raw_text)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a valid file or raw text must be provided.",
        )

    llm_client = get_llm_client()
    analysis = await analyze_document_pipeline(
        llm_client=llm_client,
        pages_text=pages,
        role=role,
        language=language,
        reading_level=reading_level,
        doc_type=doc_type,
        pii_mask=pii_mask,
    )
    return analysis


@router.post("/analyze/stream")
async def analyze_document_stream(
    file: UploadFile | None = File(None),
    raw_text: str | None = Form(None),
    role: RoleEnum = Form(RoleEnum.GENERIC),
    language: LanguageEnum = Form(LanguageEnum.ENGLISH),
    reading_level: ReadingLevelEnum = Form(ReadingLevelEnum.STANDARD),
    doc_type: str = Form("generic"),
    pii_mask: bool = Form(False),
):
    """Server-Sent Events (SSE) streaming endpoint for analysis progress."""
    content: bytes | None = None
    filename: str = "uploaded.txt"
    if file:
        content = await file.read()
        filename = file.filename or "uploaded.txt"

    async def event_generator():
        # Step 1: Ingest
        yield f"data: {json.dumps({'stage': 'ingesting', 'progress': 20, 'message': 'Extracting document text...'})}\n\n"
        await asyncio.sleep(0.05)

        if content:
            pages = await asyncio.to_thread(extract_text_from_bytes, filename, content)
        elif raw_text and raw_text.strip():
            pages = extract_text_from_raw_string(raw_text)
        else:
            yield f"data: {json.dumps({'stage': 'error', 'message': 'No document text provided'})}\n\n"
            return

        # Step 2: Chunking & Masking
        yield f"data: {json.dumps({'stage': 'chunking', 'progress': 40, 'message': 'Segmenting into stable paragraphs...'})}\n\n"
        await asyncio.sleep(0.05)

        # Step 3: LLM Analysis
        yield f"data: {json.dumps({'stage': 'analyzing', 'progress': 65, 'message': 'Grounding legal obligations and risks...'})}\n\n"
        llm_client = get_llm_client()
        analysis = await analyze_document_pipeline(
            llm_client=llm_client,
            pages_text=pages,
            role=role,
            language=language,
            reading_level=reading_level,
            doc_type=doc_type,
            pii_mask=pii_mask,
        )

        # Step 4: Quote Verification
        yield f"data: {json.dumps({'stage': 'verifying', 'progress': 90, 'message': f'Verified {analysis.verification_score}% of citations deterministically.'})}\n\n"
        await asyncio.sleep(0.05)

        # Step 5: Complete
        yield f"data: {json.dumps({'stage': 'complete', 'progress': 100, 'result': analysis.model_dump()})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/qa", response_model=QAResponse)
async def grounded_qa_endpoint(request: QARequest):
    """Answer question strictly grounded in document text with citation verification."""
    paragraphs = request.paragraphs
    if not paragraphs:
        if request.document_text:
            pages = extract_text_from_raw_string(request.document_text)
            paragraphs = chunk_document(pages)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'paragraphs' or 'document_text' must be provided.",
            )

    llm_client = get_llm_client()
    return await execute_grounded_qa(
        llm_client=llm_client,
        paragraphs=paragraphs,
        question=request.question,
        role=request.role,
        language=request.language,
    )


@router.post("/compare", response_model=CompareResponse)
async def compare_documents_endpoint(request: CompareRequest):
    """Compare two contracts and align by clause category with evidence."""
    pages_a = extract_text_from_raw_string(request.doc_a_text)
    pages_b = extract_text_from_raw_string(request.doc_b_text)
    paras_a = chunk_document(pages_a)
    paras_b = chunk_document(pages_b)

    llm_client = get_llm_client()
    return await execute_compare(
        llm_client=llm_client,
        paragraphs_a=paras_a,
        paragraphs_b=paras_b,
        role=request.role,
        language=request.language,
        doc_a_name=request.doc_a_name or "Document A",
        doc_b_name=request.doc_b_name or "Document B",
    )


@router.post("/export/ics")
async def export_ics_endpoint(analysis: DocumentAnalysisResponse):
    """Generate RFC 5545 iCalendar (.ics) file from obligations and deadlines."""
    ics_content = generate_ics_calendar(analysis)
    return PlainTextResponse(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="clausecompass_deadlines_{analysis.doc_type}.ics"'},
    )


@router.post("/export/brief")
async def export_lawyer_brief_endpoint(analysis: DocumentAnalysisResponse):
    """Generate Markdown 'Questions for your lawyer' brief."""
    brief_content = generate_lawyer_brief(analysis)
    return PlainTextResponse(
        content=brief_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="questions_for_lawyer_{analysis.doc_type}.md"'},
    )


@router.post("/export/markdown")
async def export_markdown_endpoint(analysis: DocumentAnalysisResponse):
    """Generate full Markdown export of the analysis report."""
    md_content = generate_markdown_export(analysis)
    return PlainTextResponse(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="clausecompass_report_{analysis.doc_type}.md"'},
    )
