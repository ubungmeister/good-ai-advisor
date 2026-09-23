from app.db.database import SessionLocal
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)


QUESTION = "Co když během cesty poškodím cizí věc?"
TOP_K = 20


def get_article_number(chunk):
    # Depending on how DocumentChunk metadata
    # is named in the model.

    if hasattr(chunk, "article_number"):
        return chunk.article_number

    if hasattr(chunk, "metadata_"):
        metadata = chunk.metadata_ or {}
        return metadata.get("article_number")

    if hasattr(chunk, "chunk_metadata"):
        metadata = chunk.chunk_metadata or {}
        return metadata.get("article_number")

    return None


def main():
    repository = DocumentChunkRepository()
    db = SessionLocal()

    try:
        results = repository.search_lexical(
            db=db,
            question=QUESTION,
            limit=TOP_K,
        )

        print()
        print("=== LEXICAL SEARCH ===")
        print(f"Question: {QUESTION}")
        print()

        for rank, (chunk, score) in enumerate(
            results,
            start=1,
        ):
            article_number = get_article_number(
                chunk
            )

            print(
                f"#{rank} "
                f"Article {article_number} "
                f"score={score:.4f}"
            )

            print(
                chunk.content[:300]
                .replace("\n", " ")
            )

            print()

    finally:
        db.close()


if __name__ == "__main__":
    main()