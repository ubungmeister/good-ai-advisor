from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk


class DocumentChunkRepository:

    def search_similar(
        self,
        db: Session,
        embedding: list[float],
        limit: int = 5,
    ) -> Sequence[tuple[DocumentChunk, float]]:

        distance = DocumentChunk.embedding.cosine_distance(
            embedding
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