import time

from app.db.database import SessionLocal
from app.services.retrieval_service import RetrievalService

QUESTION = "Co když během cesty poškodím cizí věc?"


def run_search(
    retrieval_service: RetrievalService,
    db,
    number: int,
):
    start = time.perf_counter()

    results = retrieval_service.search(
        db=db,
        question=QUESTION,
        limit=5,
    )

    elapsed = time.perf_counter() - start

    print()
    print(f"=== REQUEST {number} ===")

    for rank, (chunk, score) in enumerate(
        results,
        start=1,
    ):
        print(
            f"#{rank} Article {chunk.article_number} "
            f"score={score:.4f}"
        )

    print(f"Request time: {elapsed:.2f} sec")


def main():
    print("Loading services...")

    init_start = time.perf_counter()

    retrieval_service = RetrievalService()

    init_time = time.perf_counter() - init_start

    print(
        f"Service initialization: {init_time:.2f} sec"
    )

    db = SessionLocal()

    try:
        run_search(
            retrieval_service,
            db,
            1,
        )

        run_search(
            retrieval_service,
            db,
            2,
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()