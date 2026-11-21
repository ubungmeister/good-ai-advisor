from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import EmbeddingService
from app.services.document_context import EMBEDDING_FORMAT, prepare_embedding_texts


def main():
    embedding_service = EmbeddingService()

    with SessionLocal() as db:

        chunks = db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.embedding.is_(None))
        ).all()

        print(f"Found {len(chunks)} chunks without embeddings")

        for chunk in chunks:
            text = prepare_embedding_texts([chunk], embedding_service)[0]
            embedding = embedding_service.embed_document(text)

            chunk.embedding = embedding
            chunk.chunk_metadata = {**(chunk.chunk_metadata or {}), "embedding_format": EMBEDDING_FORMAT}

            print(
                f"Embedded chunk {chunk.chunk_index}: "
                f"{len(embedding)} dimensions"
            )

        db.commit()

        print("Embeddings saved successfully")


if __name__ == "__main__":
    main()
