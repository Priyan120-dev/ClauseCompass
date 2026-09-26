"""Unit tests for missing clause checker."""
import pytest

from app.models.schemas import MissingStatusEnum
from app.services.chunker import chunk_document
from app.services.missing_clauses import check_missing_clauses


@pytest.fixture
def rental_paragraphs():
    with open("samples/rental_agreement.txt", encoding="utf-8") as f:
        text = f.read()
    return chunk_document([(1, text)])


@pytest.fixture
def freelance_v1_paragraphs():
    with open("samples/freelance_v1.txt", encoding="utf-8") as f:
        text = f.read()
    return chunk_document([(1, text)])


@pytest.fixture
def freelance_v2_paragraphs():
    with open("samples/freelance_v2.txt", encoding="utf-8") as f:
        text = f.read()
    return chunk_document([(1, text)])


def test_missing_clauses_rental(rental_paragraphs):
    results = check_missing_clauses("rental", clauses=[], paragraphs=rental_paragraphs)
    name_map = {r.clause_name: r for r in results}

    assert "Security Deposit Return & Deductions" in name_map
    assert name_map["Security Deposit Return & Deductions"].status == MissingStatusEnum.FOUND

    assert "Maintenance & Habitability Standards" in name_map
    assert name_map["Maintenance & Habitability Standards"].status == MissingStatusEnum.FOUND

    # Rent increase notice and cap is not present in the rental agreement
    assert "Rent Increase Notice & Cap" in name_map
    assert name_map["Rent Increase Notice & Cap"].status == MissingStatusEnum.NOT_FOUND
    assert name_map["Rent Increase Notice & Cap"].question_to_ask != ""
    assert name_map["Rent Increase Notice & Cap"].why_it_matters != ""


def test_missing_clauses_freelance_comparison(freelance_v1_paragraphs, freelance_v2_paragraphs):
    # In V1, kill fee / cancellation fee is missing
    res_v1 = check_missing_clauses("freelance", clauses=[], paragraphs=freelance_v1_paragraphs)
    v1_map = {r.clause_name: r for r in res_v1}
    assert v1_map["Cancellation & Kill Fee"].status == MissingStatusEnum.NOT_FOUND

    # In V2, kill fee is present
    res_v2 = check_missing_clauses("freelance", clauses=[], paragraphs=freelance_v2_paragraphs)
    v2_map = {r.clause_name: r for r in res_v2}
    assert v2_map["Cancellation & Kill Fee"].status == MissingStatusEnum.FOUND
