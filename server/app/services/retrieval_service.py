from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.embedding_service import EmbeddingService

"""
EmbeddingService creates vectors.
Repository reads data from the database.
RetrievalService combines both steps and performs the full retrieval flow.
"""

class RetrievalService:

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.document_chunk_repository = DocumentChunkRepository()

    def search(
        self,
        db: Session,
        question: str,
        limit: int = 5,
    ) -> Sequence[tuple[DocumentChunk, float]]:

        query_embedding = self.embedding_service.embed_query(
            question
        )

        return self.document_chunk_repository.search_similar(
            db=db,
            embedding=query_embedding,
            limit=limit,
        )