"""Independent database search for support procedures."""

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.models.support_knowledge_document import SupportKnowledgeChunk, SupportKnowledgeDocument


class SupportKnowledgeRepository:
    def search_semantic(
        self, db: Session, embedding: list[float], limit: int = 20,
    ) -> list[SupportKnowledgeDocument]:
        distance = SupportKnowledgeChunk.embedding.cosine_distance(embedding)
        statement = (
            select(SupportKnowledgeDocument)
            .join(SupportKnowledgeChunk)
            .where(SupportKnowledgeChunk.embedding.is_not(None))
            .where(distance <= 0.35)
            .order_by(distance)
            .limit(limit)
        )
        return list(db.scalars(statement))

    def search_lexical(
        self, db: Session, question: str, limit: int = 20,
    ) -> list[SupportKnowledgeDocument]:
        query = func.lower(func.unaccent(literal(question)))
        content = func.lower(func.unaccent(SupportKnowledgeChunk.searchable_text))
        score = func.word_similarity(query, content)
        statement = (
            select(SupportKnowledgeDocument)
            .join(SupportKnowledgeChunk)
            .where(score >= 0.25)
            .order_by(score.desc())
            .limit(limit)
        )
        return list(db.scalars(statement))
