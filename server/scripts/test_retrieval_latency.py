import time
import argparse
from uuid import UUID

from app.db.database import SessionLocal
from typing import TYPE_CHECKING
from scripts.retrieval_scope import resolve_document_scope

if TYPE_CHECKING:
    from app.services.retrieval_service import RetrievalService

QUESTION = "Co když během cesty poškodím cizí věc?"


def run_search(
    retrieval_service: "RetrievalService",
    db,
    number: int,
    product_version_id: UUID,
):
    start = time.perf_counter()

    results = retrieval_service.search(
        db=db,
        question=QUESTION,
        limit=5,
        product_version_id=product_version_id,
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
    parser = argparse.ArgumentParser(description="Measure version-scoped retrieval latency.")
    parser.add_argument("--product-version-id", type=UUID)
    args = parser.parse_args()
    from app.services.retrieval_service import RetrievalService

    print("Loading services...")

    init_start = time.perf_counter()

    retrieval_service = RetrievalService()

    init_time = time.perf_counter() - init_start

    print(
        f"Service initialization: {init_time:.2f} sec"
    )

    db = SessionLocal()

    try:
        document = resolve_document_scope(db, "VPP_CP_2021", args.product_version_id)
        run_search(
            retrieval_service,
            db,
            1,
            document.product_version_id,
        )

        run_search(
            retrieval_service,
            db,
            2,
            document.product_version_id,
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
