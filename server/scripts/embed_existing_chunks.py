from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import EmbeddingService


def main():
    embedding_service = EmbeddingService()

    with SessionLocal() as db:

        chunks = db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.embedding.is_(None))
        ).all()

        print(f"Found {len(chunks)} chunks without embeddings")

        for chunk in chunks:
            embedding = embedding_service.embed_document(
                chunk.content
            )

            chunk.embedding = embedding

            print(
                f"Embedded chunk {chunk.chunk_index}: "
                f"{len(embedding)} dimensions"
            )

        db.commit()

        print("Embeddings saved successfully")


if __name__ == "__main__":
    main()