from app.db.database import SessionLocal
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.embedding_service import EmbeddingService


def main():
    embedding_service = EmbeddingService()
    repository = DocumentChunkRepository()

    question = "Is my baggage covered if it is stolen?"

    query_embedding = embedding_service.embed_query(question)

    with SessionLocal() as db:
        results = repository.search_similar(
            db=db,
            embedding=query_embedding,
            limit=3,
        )

        print(f"Question: {question}")

        for chunk, similarity in results:
            print()
            print("Similarity:", similarity)
            print("Coverage:", chunk.coverage_code)
            print("Content:", chunk.content)


if __name__ == "__main__":
    main()