from typing import Sequence

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk


class DocumentChunkRepository:
    def search_similar(
        self,
        db: Session,
        embedding: list[float],
        limit: int = 5,
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
            .where(
                DocumentChunk.embedding.is_not(None)
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