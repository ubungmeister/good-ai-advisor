from app.db.database import SessionLocal
from app.services.embedding_service import EmbeddingService
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.services.reranker_service import RerankerService


QUESTION = (
    "Může mi pojišťovna před cestou poradit, "
    "jestli potřebuji očkování?"
)

EXPECTED_ARTICLE = 15
CANDIDATE_LIMIT = 40


def main():
    db = SessionLocal()

    embedding_service = EmbeddingService()
    repository = DocumentChunkRepository()
    reranker = RerankerService()

    try:
        query_embedding = embedding_service.embed_query(
            QUESTION
        )

        candidates = repository.search_similar(
            db=db,
            embedding=query_embedding,
            limit=CANDIDATE_LIMIT,
        )

        e5_rank = None

        for rank, (chunk, similarity) in enumerate(
            candidates,
            start=1,
        ):
            if int(chunk.article_number) == EXPECTED_ARTICLE:
                e5_rank = rank

                print("=== E5 RESULT ===")
                print(f"Rank: {rank}")
                print(f"Similarity: {similarity:.4f}")
                print()
                print(chunk.content)
                print()

                break

        reranked = reranker.rerank(
            question=QUESTION,
            candidates=list(candidates),
            limit=CANDIDATE_LIMIT,
        )

        reranker_rank = None

        for rank, (chunk, score) in enumerate(
            reranked,
            start=1,
        ):
            if int(chunk.article_number) == EXPECTED_ARTICLE:
                reranker_rank = rank

                print("=== RERANKER RESULT ===")
                print(f"Rank: {rank}")
                print(f"Score: {score:.4f}")
                print()
                print(chunk.content)
                print()

                break

        print("=== SUMMARY ===")
        print(f"E5 rank: {e5_rank}")
        print(f"Reranker rank: {reranker_rank}")

    finally:
        db.close()


if __name__ == "__main__":
    main()