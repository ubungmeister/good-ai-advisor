"""Architecture Update 1: database integration tests for RAG document scoping.

Copy to: server/app/services/test/test_rag_two_versions_integration.py
Run from server: python -m pytest app/services/test/test_rag_two_versions_integration.py -v

Requires the development PostgreSQL database and seed policy TI-2026-0001.
The fixture creates a second *temporary* ProductVersion and two documents.
It uses flush(), NEVER commit(), and ALWAYS rolls the transaction back.
No LLM API calls, model downloads, or Alembic migrations are needed.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_document import DocumentStatus, KnowledgeDocument
from app.models.policy import Policy
from app.models.product_version import ProductVersion
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.retrieval_service import RetrievalService

POLICY_NUMBER = "TI-2026-0001"
QUERY = "baggage coverage exclusions"


@pytest.fixture
def two_version_scope():
    """Create two competing scopes, without persisting any test data."""
    db = SessionLocal()
    try:
        policy = db.scalar(
            select(Policy).where(Policy.policy_number == POLICY_NUMBER)
        )
        assert policy is not None, (
            f"Seed policy {POLICY_NUMBER} not found. "
            "Run the development seed script first."
        )

        original_version = db.get(ProductVersion, policy.product_version_id)
        assert original_version is not None

        # Use an existing valid embedding so semantic queries run against real
        # pgvector data without initializing SentenceTransformers.
        original_chunk = db.scalar(
            select(DocumentChunk)
            .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeDocument.product_version_id == original_version.id,
                KnowledgeDocument.ingestion_status == DocumentStatus.READY,
                DocumentChunk.embedding.is_not(None),
            )
            .limit(1)
        )
        assert original_chunk is not None, (
            "No embedded READY chunk found for the seed policy. "
            "Check that VPP embeddings have been ingested."
        )
        query_vector = [float(value) for value in original_chunk.embedding]
        assert len(query_vector) == 384

        # Temporary version B belongs to the SAME product family but is
        # deliberately not the version purchased by the seed policy.
        other_version = ProductVersion(
            product_id=original_version.product_id,
            version=f"SCOPE_TEST_{uuid4().hex[:12]}",
            valid_from=original_version.valid_from,
            valid_to=original_version.valid_to,
            is_active=True,
        )
        db.add(other_version)
        db.flush()

        other_document = KnowledgeDocument(
            product_version_id=other_version.id,
            title="TEMPORARY other-version conditions — rollback only",
            document_type="VPP",
            version="SCOPE_TEST",
            language="en",
            ingestion_status=DocumentStatus.READY,
        )
        # A non-READY document in scope A must also be excluded.
        failed_document = KnowledgeDocument(
            product_version_id=original_version.id,
            title="TEMPORARY failed conditions — rollback only",
            document_type="VPP",
            version="SCOPE_TEST_FAILED",
            language="en",
            ingestion_status=DocumentStatus.FAILED,
        )
        db.add_all([other_document, failed_document])
        db.flush()

        other_chunk = DocumentChunk(
            document_id=other_document.id,
            chunk_index=0,
            content=QUERY,
            embedding=query_vector,
            section_title="Other product version: never visible to A",
        )
        failed_chunk = DocumentChunk(
            document_id=failed_document.id,
            chunk_index=0,
            content=QUERY,
            embedding=query_vector,
            section_title="FAILED document: never visible to retrieval",
        )
        db.add_all([other_chunk, failed_chunk])
        db.flush()

        yield SimpleNamespace(
            db=db,
            version_a=original_version.id,
            version_b=other_version.id,
            chunk_b=other_chunk.id,
            forbidden_failed_chunk=failed_chunk.id,
            query_vector=query_vector,
        )
    finally:
        # No commit anywhere in this fixture: test records are discarded.
        db.rollback()
        db.close()


def _check_results(scope, results, *, expected_version):
    assert results, "Expected at least one matching document chunk"
    for chunk, _ in results:
        document = scope.db.get(KnowledgeDocument, chunk.document_id)
        assert document is not None
        assert document.product_version_id == expected_version
        assert document.ingestion_status == DocumentStatus.READY
        assert chunk.id != scope.forbidden_failed_chunk


def test_semantic_and_lexical_search_isolate_both_versions(two_version_scope):
    scope = two_version_scope
    repository = DocumentChunkRepository()

    for method, params in (
        (repository.search_similar, {"embedding": scope.query_vector}),
        (repository.search_lexical, {"question": QUERY}),
    ):
        results_a = method(
            db=scope.db, product_version_id=scope.version_a, limit=20, **params
        )
        results_b = method(
            db=scope.db, product_version_id=scope.version_b, limit=20, **params
        )
        _check_results(scope, results_a, expected_version=scope.version_a)
        _check_results(scope, results_b, expected_version=scope.version_b)

        assert scope.chunk_b not in {chunk.id for chunk, _ in results_a}
        assert {chunk.id for chunk, _ in results_b} == {scope.chunk_b}


def test_full_hybrid_pipeline_keeps_scope(two_version_scope):
    scope = two_version_scope
    # Exercise the REAL RetrievalService branches, RRF, and candidate selection,
    # while replacing only the ML embedding/reranker calls for a fast DB test.
    service = RetrievalService.__new__(RetrievalService)
    service.document_chunk_repository = DocumentChunkRepository()
    service.embedding_service = SimpleNamespace(
        embed_query=lambda question: scope.query_vector
    )
    service.lexical_query_builder = SimpleNamespace(build=lambda question: question)
    service.reranker_service = SimpleNamespace(
        rerank=lambda *, question, candidates, limit: candidates[:limit]
    )

    for version in (scope.version_a, scope.version_b):
        result = service.search(
            db=scope.db,
            question=QUERY,
            limit=5,
            product_version_id=version,
        )
        _check_results(scope, result, expected_version=version)


def test_unknown_version_returns_no_documents(two_version_scope):
    scope = two_version_scope
    repository = DocumentChunkRepository()
    unknown_version_id = uuid4()

    assert repository.search_lexical(
        db=scope.db,
        question=QUERY,
        limit=5,
        product_version_id=unknown_version_id,
    ) == []
    assert repository.search_similar(
        db=scope.db,
        embedding=scope.query_vector,
        limit=5,
        product_version_id=unknown_version_id,
    ) == []
