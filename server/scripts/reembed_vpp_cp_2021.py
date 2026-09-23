from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_document import KnowledgeDocument
from app.services.embedding_service import EmbeddingService


DOCUMENT_VERSION = "VPP_CP_2021"


def main():
    db = SessionLocal()

    try:
        print("=== RE-EMBED VPP CP 2021 ===")

        document = db.scalar(
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.version
                == DOCUMENT_VERSION
            )
        )

        if document is None:
            raise ValueError(
                f"KnowledgeDocument not found: "
                f"{DOCUMENT_VERSION}"
            )

        chunks = db.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id
                == document.id
            )
            .order_by(
                DocumentChunk.chunk_index
            )
        ).all()

        if not chunks:
            raise ValueError(
                "No document chunks found."
            )

        print(
            f"Chunks found: {len(chunks)}"
        )

        embedding_service = EmbeddingService()

        texts = [
            chunk.content
            for chunk in chunks
        ]

        print(
            "Generating new embeddings..."
        )

        embeddings = (
            embedding_service.embed_documents(
                texts
            )
        )

        if len(embeddings) != len(chunks):
            raise ValueError(
                "Embedding count does not "
                "match chunk count."
            )

        print(
            "Updating database..."
        )

        for chunk, embedding in zip(
            chunks,
            embeddings,
        ):
            chunk.embedding = embedding

        db.commit()

        print()
        print("=== COMPLETE ===")
        print(
            f"Updated chunks: {len(chunks)}"
        )
        print(
            f"Dimensions: "
            f"{len(embeddings[0])}"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()