"""Unit tests for document comparison service."""
import pytest

from app.llm.fake import FakeLLMClient
from app.models.schemas import DiffTypeEnum, RiskDeltaEnum, RoleEnum
from app.services.chunker import chunk_document
from app.services.compare import execute_compare


@pytest.fixture
def freelance_v1_paras():
    with open("samples/freelance_v1.txt", encoding="utf-8") as f:
        text = f.read()
    return chunk_document([(1, text)])


@pytest.fixture
def freelance_v2_paras():
    with open("samples/freelance_v2.txt", encoding="utf-8") as f:
        text = f.read()
    return chunk_document([(1, text)])


@pytest.mark.asyncio
async def test_compare_freelance_versions(freelance_v1_paras, freelance_v2_paras):
    client = FakeLLMClient()
    response = await execute_compare(
        llm_client=client,
        paragraphs_a=freelance_v1_paras,
        paragraphs_b=freelance_v2_paras,
        role=RoleEnum.FREELANCER,
        doc_a_name="Freelance V1",
        doc_b_name="Freelance V2",
    )

    assert response.total_differences >= 4
    categories = {it.category: it for it in response.items}

    # IP timing change
    assert "Intellectual Property" in categories
    ip_item = categories["Intellectual Property"]
    assert ip_item.diff_type == DiffTypeEnum.MODIFIED
    assert ip_item.risk_delta == RiskDeltaEnum.DECREASED
    assert "Contractor" in ip_item.who_benefits

    # Non-solicitation added
    assert "Non-Solicitation" in categories
    nonsol_item = categories["Non-Solicitation"]
    assert nonsol_item.diff_type == DiffTypeEnum.ADDED
