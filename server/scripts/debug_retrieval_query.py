from app.db.database import SessionLocal
from app.services.retrieval_service import RetrievalService


QUESTION = "Co když během cesty poškodím cizí věc?"
TOP_K = 200


def main():
    retrieval_service = RetrievalService()
    db = SessionLocal()

    try:
        results = retrieval_service.search(
            db=db,
            question=QUESTION,
            limit=TOP_K,
        )

        print("=== RETRIEVAL DEBUG ===")
        print()
        print(f"Question: {QUESTION}")
        print(f"Top K: {TOP_K}")
        print()

        for rank, (chunk, similarity) in enumerate(
                results,
                start=1,
        ):
            if int(chunk.article_number) == 21:
                print("=== ARTICLE 21 FOUND ===")
                print(f"Rank: {rank}")
                print(f"Similarity: {similarity:.4f}")
                print(f"Chunk index: {chunk.chunk_index}")
                print()
                print(chunk.content)
        # for rank, (chunk, similarity) in enumerate(
        #     results,
        #     start=1,
        # ):
        #     print(f"--- RANK {rank} ---")
        #     print(f"Article: {chunk.article_number}")
        #     print(f"Similarity: {similarity:.4f}")
        #     print(f"Chunk index: {chunk.chunk_index}")
        #     print()
        #
        #     print(chunk.content)
        #     print()
        #     print()

    finally:
        db.close()


if __name__ == "__main__":
    main()