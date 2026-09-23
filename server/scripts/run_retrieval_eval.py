from app.db.database import SessionLocal
from app.services.retrieval_eval_loader import RetrievalEvalLoader
from app.services.retrieval_service import RetrievalService


EVAL_FILE = "data/evals/retrieval_eval.json"
TOP_K = 10


def main():
    loader = RetrievalEvalLoader()
    dataset = loader.load(EVAL_FILE)

    retrieval_service = RetrievalService()

    db = SessionLocal()

    try:
        print("=== RETRIEVAL EVALUATION ===")
        print()

        hit_at_1 = 0
        hit_at_3 = 0
        hit_at_5 = 0
        reciprocal_rank_sum = 0.0

        for case in dataset.cases:
            results = retrieval_service.search(
                db=db,
                question=case.question,
                limit=TOP_K,
            )

            found_rank = None

            for rank, (chunk, similarity) in enumerate(
                results,
                start=1,
            ):
                article_number = int(chunk.article_number)

                if article_number in case.expected_articles:
                    found_rank = rank
                    break

            print(case.id)
            print(f"  question: {case.question}")
            print(f"  expected: {case.expected_articles}")
            print(f"  found rank: {found_rank}")
            print()

            if found_rank is not None:
                if found_rank <= 1:
                    hit_at_1 += 1

                if found_rank <= 3:
                    hit_at_3 += 1

                if found_rank <= 5:
                    hit_at_5 += 1

                reciprocal_rank_sum += 1 / found_rank

        total = len(dataset.cases)

        print("=== RESULTS ===")
        print()

        print(f"Queries: {total}")
        print(f"Hit@1: {hit_at_1 / total:.2%}")
        print(f"Hit@3: {hit_at_3 / total:.2%}")
        print(f"Hit@5: {hit_at_5 / total:.2%}")
        print(f"MRR: {reciprocal_rank_sum / total:.3f}")

    finally:
        db.close()


if __name__ == "__main__":
    main()