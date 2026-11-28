from datetime import date
from pathlib import Path

import pytest

from app.services.support_knowledge_loader import SupportKnowledgeLoader
from app.services.support_publication import SupportPublicationGate
from app.schemas.support_knowledge import SupportProcedure


def approved_procedure(**overrides):
    procedure = {
        "id": "SUP_TEST_001",
        "document_type": "support_procedure",
        "schema_version": "1.0",
        "language": "cs",
        "category": "baggage",
        "title": "Nahlášení škody",
        "scenario": "Klient hlásí škodu.",
        "intent_tag": "claim_report",
        "question_variations": ["Jak nahlásím škodu?"],
        "conditions": ["Událost musí být doložitelná."],
        "immediate_steps": [{"text": "Uchovejte doklady.", "requirement_type": "recommended"}],
        "required_documents": ["Potvrzení o události"],
        "recommended_documents": [],
        "police_involvement": None,
        "clarifying_questions": [],
        "coverage_considerations": [],
        "escalation_conditions": ["Pokud chybí doklady, kontaktujte podporu."],
        "open_questions_for_expert": [],
        "sources": [{"source_id": "GUIDE", "title": "Official guide", "url": "https://example.test/guide"}],
        "source_ids": ["GUIDE"],
        "evidence_level": "official_insurer",
        "official_scenario_specific_evidence": True,
        "procedure_completeness": "complete",
        "priority": "P1",
        "policy_version_check_required": False,
        "applicable_policy_versions": ["VPP_CP_2021"],
        "review_status": "APPROVED",
        "reviewed_by": "expert@example.test",
        "last_verified_at": "2026-11-01",
        "last_public_source_checked_at": "2026-11-01",
        "approved_at": "2026-11-02",
        "publication_status": "PUBLISHED",
        "retrieval_eligible": True,
        "notes_for_reviewer": None,
    }
    procedure.update(overrides)
    return SupportProcedure.model_validate(procedure)


def test_loader_reads_all_processed_support_procedures():
    collection = SupportKnowledgeLoader().load_directory(
        Path(__file__).resolve().parents[2] / "data/knowledge/support/processed"
    )

    assert len(collection.procedures) == 148
    assert {procedure.language for procedure in collection.procedures} == {"cs"}
    assert all(not procedure.retrieval_eligible for procedure in collection.procedures)


def test_publication_gate_requires_approval_provenance_and_explicit_scope():
    gate = SupportPublicationGate()
    procedure = approved_procedure()

    assert gate.is_eligible(procedure, product_version="VPP_CP_2021", as_of=date(2026, 11, 26))

    for field, value in (
        ("publication_status", "REVIEW_ONLY"),
        ("retrieval_eligible", False),
        ("reviewed_by", None),
        ("approved_at", None),
        ("applicable_policy_versions", []),
    ):
        blocked = procedure.model_copy(update={field: value})
        assert not gate.is_eligible(blocked, product_version="VPP_CP_2021", as_of=date(2026, 11, 26))


def test_gate_rejects_expired_procedure_and_wrong_product_version():
    gate = SupportPublicationGate()
    procedure = approved_procedure(
        effective_from="2027-01-01",
        effective_to="2027-12-31",
    )

    assert not gate.is_eligible(procedure, product_version="VPP_CP_2021", as_of=date(2026, 11, 26))
    assert not gate.is_eligible(procedure, product_version="VPP_CP_2021", as_of=date(2028, 1, 1))
    assert not gate.is_eligible(procedure, product_version="OTHER", as_of=date(2027, 6, 1))


def test_loader_rejects_invalid_support_documents():
    with pytest.raises(ValueError):
        SupportKnowledgeLoader().load_data({"dataset_status": "DRAFT"})
