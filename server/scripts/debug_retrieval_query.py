import argparse
from uuid import UUID

from app.db.database import SessionLocal
from scripts.retrieval_scope import resolve_document_scope


QUESTION = "Co když během cesty poškodím cizí věc?"
TOP_K = 200


def main():
    parser = argparse.ArgumentParser(description="Inspect version-scoped retrieval results.")
    parser.add_argument("--product-version-id", type=UUID)
    args = parser.parse_args()
    from app.services.retrieval_service import RetrievalService

    retrieval_service = RetrievalService()
    db = SessionLocal()

    try:
        document = resolve_document_scope(db, "VPP_CP_2021", args.product_version_id)
        results = retrieval_service.search(
            db=db,
            question=QUESTION,
            limit=TOP_K,
            product_version_id=document.product_version_id,
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
