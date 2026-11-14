"""Scope regression tests for the three hybrid RAG retrieval branches.

Copy into `server/app/services/test/test_rag_document_scoping.py`.
Run: python -m pytest app/services/test/test_rag_document_scoping.py -v
"""
import uuid
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.retrieval_service import RetrievalService


def _compiled_last_statement(db):
    statement = db.execute.call_args.args[0]
    return statement, statement.compile(dialect=postgresql.dialect())


def _verify_scope(statement, compiled, selected_version):
    sql = str(compiled)
    assert "JOIN knowledge_documents" in sql
    assert "knowledge_documents.product_version_id" in sql
    assert "knowledge_documents.ingestion_status" in sql
    # Confirm a bind parameter carries the requested version; no string interpolation.
    assert selected_version in compiled.params.values()
    assert "READY" not in sql  # the READY value is bound, not interpolated


def test_semantic_query_is_scoped_to_ready_documents_of_selected_version():
    version = uuid.uuid4()
    db = Mock()
    db.execute.return_value.all.return_value = []
    DocumentChunkRepository().search_similar(
        db=db,
        embedding=[0.0] * 384,
        limit=20,
        product_version_id=version,
    )
    statement, compiled = _compiled_last_statement(db)
    _verify_scope(statement, compiled, version)
    assert "document_chunks.embedding IS NOT NULL" in str(compiled)


def test_lexical_query_is_scoped_to_ready_documents_of_selected_version():
    version = uuid.uuid4()
    db = Mock()
    db.execute.return_value.all.return_value = []
    DocumentChunkRepository().search_lexical(
        db=db,
        question="baggage exclusions",
        limit=20,
        product_version_id=version,
    )
    statement, compiled = _compiled_last_statement(db)
    _verify_scope(statement, compiled, version)


def test_all_three_retrievers_receive_the_same_version():
    version = uuid.uuid4()
    service = RetrievalService.__new__(RetrievalService)  # avoid loading local ML models
    service.embedding_service = Mock()
    service.embedding_service.embed_query.return_value = [0.0] * 384
    service.document_chunk_repository = Mock()
    service.document_chunk_repository.search_similar.return_value = []
    service.document_chunk_repository.search_lexical.return_value = []
    service.lexical_query_builder = Mock()
    service.lexical_query_builder.build.return_value = "baggage"
    service.reranker_service = Mock()
    service.reranker_service.rerank.return_value = []

    result = service.search(
        db=Mock(), question="baggage insurance", limit=5,
        product_version_id=version,
    )

    assert result == []
    assert service.document_chunk_repository.search_similar.call_args.kwargs["product_version_id"] == version
    assert service.document_chunk_repository.search_lexical.call_count == 2
    for call in service.document_chunk_repository.search_lexical.call_args_list:
        assert call.kwargs["product_version_id"] == version


def test_unscoped_retrieval_is_not_allowed():
    service = RetrievalService.__new__(RetrievalService)
    with pytest.raises(TypeError, match="product_version_id"):
        service.search(db=Mock(), question="baggage insurance")
