import argparse
from uuid import UUID

from app.db.database import SessionLocal
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from scripts.retrieval_scope import resolve_document_scope


QUESTION = "Je moje zavazadlo pojištěné proti krádeži?"
LIMIT = 5


def main():
    parser = argparse.ArgumentParser(description="Test version-scoped semantic retrieval.")
    parser.add_argument("--product-version-id", type=UUID)
    args = parser.parse_args()
    db = SessionLocal()

    try:
        document = resolve_document_scope(db, "VPP_CP_2021", args.product_version_id)
        from app.services.embedding_service import EmbeddingService

        print("=== REAL RETRIEVAL TEST ===")
        print()

        print(f"Question: {QUESTION}")
        print()

        embedding_service = EmbeddingService()
        repository = DocumentChunkRepository()

        # Convert user question into query embedding.
        query_embedding = embedding_service.embed_query(
            QUESTION
        )

        # Find the most semantically similar chunks
        # in PostgreSQL / pgvector.
        results = repository.search_similar(
            db=db,
            embedding=query_embedding,
            limit=LIMIT,
            product_version_id=document.product_version_id,
        )

        print(f"Results: {len(results)}")
        print()

        for index, (chunk, similarity) in enumerate(
            results,
            start=1,
        ):
            print("=" * 80)
            print(f"Result #{index}")
            print(f"Similarity: {similarity:.4f}")
            print(f"Article: {chunk.article_number}")
            print(f"Section: {chunk.section_title}")
            print(f"Page: {chunk.page_number}")
            print()
            print(chunk.content)
            print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
