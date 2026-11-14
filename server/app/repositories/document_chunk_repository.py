import uuid
from typing import Sequence

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.models.knowledge_document import DocumentStatus, KnowledgeDocument


class DocumentChunkRepository:
    def search_similar(
        self,
        db: Session,
        embedding: list[float],
        limit: int = 5,
        *,
        product_version_id: uuid.UUID,
    ) -> Sequence[
        tuple[DocumentChunk, float]
    ]:
        """
        Semantic search using pgvector.
        """

        distance = (
            DocumentChunk.embedding.cosine_distance(
                embedding
            )
        ).label("distance")

        statement = (
            select(
                DocumentChunk,
                distance,
            )
            .join(
                KnowledgeDocument,
                DocumentChunk.document_id == KnowledgeDocument.id,
            )
            .where(
                KnowledgeDocument.product_version_id == product_version_id,
                KnowledgeDocument.ingestion_status == DocumentStatus.READY,
                DocumentChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(limit)
        )

        rows = db.execute(statement).all()

        return [
            (
                row[0],
                1 - float(row[1]),
            )
            for row in rows
        ]

    def search_lexical(
        self,
        db: Session,
        question: str,
        limit: int = 20,
        *,
        product_version_id: uuid.UUID,
    ) -> Sequence[
        tuple[DocumentChunk, float]
    ]:
        """
        Lexical/fuzzy search using PostgreSQL pg_trgm.

        This search looks at similarity of actual wording,
        while search_similar() searches by semantic meaning.
        """

        normalized_question = func.lower(
            func.unaccent(
                literal(question)
            )
        )

        normalized_content = func.lower(
            func.unaccent(
                DocumentChunk.content
            )
        )

        lexical_score = func.word_similarity(
            normalized_question,
            normalized_content,
        ).label("lexical_score")

        statement = (
            select(
                DocumentChunk,
                lexical_score,
            )
            .join(
                KnowledgeDocument,
                DocumentChunk.document_id == KnowledgeDocument.id,
            )
            .where(
                KnowledgeDocument.product_version_id == product_version_id,
                KnowledgeDocument.ingestion_status == DocumentStatus.READY,
            )
            .order_by(
                lexical_score.desc()
            )
            .limit(limit)
        )

        rows = db.execute(statement).all()

        return [
            (
                row[0],
                float(row[1]),
            )
            for row in rows
        ]