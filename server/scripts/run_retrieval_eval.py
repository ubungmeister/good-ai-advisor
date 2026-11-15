import argparse
from pathlib import Path
from uuid import UUID

from app.db.database import SessionLocal
from app.services.retrieval_eval_loader import RetrievalEvalLoader
from scripts.retrieval_scope import resolve_document_scope


EVAL_FILE = Path(__file__).resolve().parents[1] / "data/evals/retrieval_eval.json"
TOP_K = 10


def evaluate(db, retrieval_service, dataset, document):
    """Measure article hits within the dataset's document, preserving global ranks."""
    hit_counts = {1: 0, 3: 0, 5: 0}
    reciprocal_rank_sum = 0.0
    for case in dataset.cases:
        results = retrieval_service.search(
            db=db, question=case.question, limit=TOP_K,
            product_version_id=document.product_version_id,
        )
        found_rank = None
        for rank, (chunk, _score) in enumerate(results, start=1):
            if chunk.document_id != document.id:
                continue
            try:
                article_number = int(chunk.article_number)
            except (TypeError, ValueError):
                continue
            if article_number in case.expected_articles:
                found_rank = rank
                break
        print(f"{case.id}: rank={found_rank}, expected={case.expected_articles}")
        if found_rank is not None:
            for k in hit_counts:
                hit_counts[k] += int(found_rank <= k)
            reciprocal_rank_sum += 1 / found_rank
    total = len(dataset.cases)
    return {
        "queries": total,
        **{f"hit@{k}": count / total for k, count in hit_counts.items()},
        "mrr": reciprocal_rank_sum / total,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate version-scoped retrieval.")
    parser.add_argument("--product-version-id", type=UUID)
    parser.add_argument("--eval-file", type=Path, default=EVAL_FILE)
    args = parser.parse_args()
    loader = RetrievalEvalLoader()
    dataset = loader.load(str(args.eval_file))

    db = SessionLocal()

    try:
        document = resolve_document_scope(db, dataset.document_code, args.product_version_id)
        from app.services.retrieval_service import RetrievalService

        retrieval_service = RetrievalService()
        print("=== RETRIEVAL EVALUATION ===")
        print(f"Document: {document.id}; product version: {document.product_version_id}")
        metrics = evaluate(db, retrieval_service, dataset, document)
        for name, value in metrics.items():
            print(f"{name}: {value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
