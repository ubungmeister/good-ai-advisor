"""Candidate recall and scope contracts without model downloads or database writes."""

from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

from sqlalchemy.dialects import postgresql

from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.document_context import section_label, reranker_text
from app.services.retrieval_service import RetrievalService


def rows(count):
    return [(SimpleNamespace(id=uuid4()), 1.0 / (index + 1)) for index in range(count)]


def test_semantic_window_and_protected_lexical_hits_survive_crowding():
    service = RetrievalService.__new__(RetrievalService)
    semantic = rows(service.SEMANTIC_LIMIT)
    original, expanded, fused = rows(20), rows(20), rows(100)
    candidates = service._build_protected_candidates(semantic, original, expanded, fused)
    ids = {chunk.id for chunk, _ in candidates}
    assert {chunk.id for chunk, _ in semantic[:service.SEMANTIC_PROTECTED]}.issubset(ids)
    assert {chunk.id for chunk, _ in original[:service.ORIGINAL_LEXICAL_PROTECTED]}.issubset(ids)
    assert {chunk.id for chunk, _ in expanded[:service.STANZA_LEXICAL_PROTECTED]}.issubset(ids)
    assert len(candidates) == len(ids) == service.RERANKER_CANDIDATE_LIMIT


def test_overlapping_channels_do_not_duplicate_candidates_or_displace_unique_hits():
    service = RetrievalService.__new__(RetrievalService)
    semantic = rows(service.SEMANTIC_LIMIT)
    unique_lexical = rows(1)
    lexical = [*semantic[:4], *unique_lexical]
    candidates = service._build_protected_candidates(semantic, lexical, lexical, semantic)
    assert len(candidates) == service.RERANKER_CANDIDATE_LIMIT
    assert len({chunk.id for chunk, _ in candidates}) == len(candidates)
    assert unique_lexical[0][0].id in {chunk.id for chunk, _ in candidates}


def test_lexical_body_signal_and_document_scope_are_preserved():
    repository = DocumentChunkRepository()
    db = Mock()
    db.execute.return_value.all.return_value = []
    version = uuid4()
    repository.search_lexical(db=db, question="policy question", product_version_id=version)
    statement = db.execute.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "concat_ws" not in sql
    assert "knowledge_documents.product_version_id =" in sql
    assert "knowledge_documents.ingestion_status =" in sql
    assert version in compiled.params.values()
    assert "READY" in compiled.params.values()


def test_context_is_available_to_reranker_without_replacing_original_clause():
    chunk = SimpleNamespace(content="Report the incident to the police.",
        section_title="Duties", chunk_metadata={"part_title": "Baggage insurance"})
    assert section_label(chunk) == "Baggage insurance / Duties"
    assert reranker_text(chunk).endswith(chunk.content)
    assert chunk.content == "Report the incident to the police."
    chunk.chunk_metadata = None
    chunk.section_title = None
    assert reranker_text(chunk) == chunk.content
