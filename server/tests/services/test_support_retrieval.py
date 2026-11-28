from datetime import date

from app.schemas.support_knowledge import SupportProcedure
from app.services.support_publication import SupportPublicationGate
from app.services.support_retrieval import SupportRetrievalService


def procedure(*, published: bool) -> SupportProcedure:
    return SupportProcedure.model_validate({
        "id": "SUP_TEST_001",
        "document_type": "support_procedure",
        "schema_version": "1.0",
        "language": "cs",
        "category": "baggage",
        "title": "Nahlášení škody na zavazadle",
        "scenario": "Klient hlásí škodu na zavazadle.",
        "intent_tag": "baggage_claim",
        "question_variations": ["Jak nahlásím škodu na zavazadle?"],
        "conditions": ["Uchovejte doklady."],
        "immediate_steps": [{"text": "Kontaktujte podporu.", "requirement_type": "recommended"}],
        "required_documents": ["Potvrzení o události"],
        "recommended_documents": [],
        "police_involvement": None,
        "clarifying_questions": [],
        "coverage_considerations": [],
        "escalation_conditions": ["Chybějící dokumenty"],
        "open_questions_for_expert": [],
        "sources": [{"source_id": "GUIDE", "url": "https://example.test/guide"}],
        "source_ids": ["GUIDE"],
        "evidence_level": "official_insurer",
        "official_scenario_specific_evidence": True,
        "procedure_completeness": "complete",
        "priority": "P1",
        "policy_version_check_required": False,
        "applicable_policy_versions": ["VPP_CP_2021"],
        "review_status": "APPROVED" if published else "DRAFT",
        "reviewed_by": "expert" if published else None,
        "approved_at": "2026-11-01" if published else None,
        "publication_status": "PUBLISHED" if published else "REVIEW_ONLY",
        "retrieval_eligible": published,
    })


def test_retrieval_returns_complete_support_evidence_unit():
    service = SupportRetrievalService(
        procedures=[procedure(published=True)],
        publication_gate=SupportPublicationGate(),
    )

    result = service.search(
        question="Jak nahlásím škodu na zavazadle?",
        product_version="VPP_CP_2021",
        as_of=date(2026, 11, 26),
    )

    assert not result.is_miss
    assert result.units[0].required_documents == ["Potvrzení o události"]
    assert result.units[0].escalation_guidance == ["Chybějící dokumenty"]


def test_retrieval_miss_never_returns_draft_procedure():
    service = SupportRetrievalService(
        procedures=[procedure(published=False)],
        publication_gate=SupportPublicationGate(),
    )

    result = service.search(
        question="Jak nahlásím škodu na zavazadle?",
        product_version="VPP_CP_2021",
        as_of=date(2026, 11, 26),
    )

    assert result.is_miss
    assert result.units == []
