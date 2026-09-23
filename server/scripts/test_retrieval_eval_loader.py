from app.services.retrieval_eval_loader import (
    RetrievalEvalLoader,
)


EVAL_FILE = (
    "data/evals/retrieval_eval.json"
)


def main():
    loader = RetrievalEvalLoader()

    dataset = loader.load(
        EVAL_FILE
    )

    print("=== RETRIEVAL EVAL DATASET ===")
    print()

    print(
        f"Document: "
        f"{dataset.document_code}"
    )

    print(
        f"Cases: "
        f"{len(dataset.cases)}"
    )

    print()
    print("Questions:")
    print()

    for case in dataset.cases:
        print(
            f"{case.id}"
        )

        print(
            f"  Category: "
            f"{case.category}"
        )

        print(
            f"  Language: "
            f"{case.language}"
        )

        print(
            f"  Question: "
            f"{case.question}"
        )

        print(
            f"  Expected articles: "
            f"{case.expected_articles}"
        )

        print()


if __name__ == "__main__":
    main()