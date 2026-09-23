from app.db.database import SessionLocal
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)


SEARCH_LIMIT = 200


TEST_CASES = [
    {
        "id": "baggage_theft_police_report",
        "expected_article": 37,
        "original_query": (
            "Musím krádež zavazadla v zahraničí "
            "nahlásit policii a doložit policejní protokol?"
        ),
        "focused_query": (
            "krádež zavazadla policii policejní protokol"
        ),
    },
    {
        "id": "baggage_damage_repair",
        "expected_article": 38,
        "original_query": (
            "Jak pojišťovna postupuje, když se moje "
            "zavazadlo poškodí a je možné ho opravit?"
        ),
        "focused_query": (
            "poškození zavazadla oprava"
        ),
    },
    {
        "id": "baggage_passport_exclusion",
        "expected_article": 39,
        "original_query": (
            "Je cestovní pas pojištěný v rámci "
            "pojištění zavazadel?"
        ),
        "focused_query": (
            "cestovní pas zavazadla"
        ),
    },
]


def get_article_number(chunk) -> int | None:
    article_number = getattr(
        chunk,
        "article_number",
        None,
    )

    if article_number is None:
        return None

    try:
        return int(article_number)

    except (TypeError, ValueError):
        return None


def find_expected_article(
    results,
    expected_article: int,
):
    matches = []

    for rank, (
        chunk,
        score,
    ) in enumerate(
        results,
        start=1,
    ):
        article_number = get_article_number(
            chunk
        )

        if article_number == expected_article:
            matches.append(
                (
                    rank,
                    chunk,
                    score,
                )
            )

    return matches


def print_expected_rank(
    label: str,
    results,
    expected_article: int,
):
    matches = find_expected_article(
        results=results,
        expected_article=expected_article,
    )

    if not matches:
        print(
            f"{label}: "
            f"Article {expected_article} -> NOT FOUND"
        )

        return

    for rank, chunk, score in matches:
        print(
            f"{label}: "
            f"Article {expected_article} "
            f"-> rank={rank}, "
            f"score={score:.4f}"
        )


def print_top_results(
    label: str,
    results,
    limit: int = 10,
):
    print()
    print(
        f"--- {label} TOP {limit} ---"
    )

    for rank, (
        chunk,
        score,
    ) in enumerate(
        results[:limit],
        start=1,
    ):
        article_number = get_article_number(
            chunk
        )

        print(
            f"#{rank:02d} "
            f"Article {article_number} "
            f"score={score:.4f}"
        )


def main():
    repository = DocumentChunkRepository()

    db = SessionLocal()

    try:
        print()
        print(
            "========================================"
        )
        print(
            "LEXICAL QUERY VARIANT DEBUG"
        )
        print(
            "========================================"
        )

        for case in TEST_CASES:

            expected_article = (
                case["expected_article"]
            )

            print()
            print()
            print(
                "=" * 70
            )

            print(
                f"CASE: {case['id']}"
            )

            print(
                f"EXPECTED ARTICLE: "
                f"{expected_article}"
            )

            print(
                "=" * 70
            )

            # ==========================================
            # Variant 1
            # Current behaviour:
            # send the complete user question
            # to lexical search.
            # ==========================================

            original_query = (
                case["original_query"]
            )

            original_results = list(
                repository.search_lexical(
                    db=db,
                    question=original_query,
                    limit=SEARCH_LIMIT,
                )
            )

            print()
            print(
                "ORIGINAL QUERY:"
            )

            print(
                original_query
            )

            print_expected_rank(
                label="Original lexical",
                results=original_results,
                expected_article=expected_article,
            )

            # ==========================================
            # Variant 2
            # Diagnostic only:
            #
            # remove conversational / generic words
            # and keep important lexical concepts.
            #
            # This is NOT the proposed production
            # implementation yet.
            # ==========================================

            focused_query = (
                case["focused_query"]
            )

            focused_results = list(
                repository.search_lexical(
                    db=db,
                    question=focused_query,
                    limit=SEARCH_LIMIT,
                )
            )

            print()
            print(
                "FOCUSED QUERY:"
            )

            print(
                focused_query
            )

            print_expected_rank(
                label="Focused lexical",
                results=focused_results,
                expected_article=expected_article,
            )

            # ==========================================
            # Compare top results
            # ==========================================

            print_top_results(
                label="ORIGINAL",
                results=original_results,
                limit=10,
            )

            print_top_results(
                label="FOCUSED",
                results=focused_results,
                limit=10,
            )

        print()
        print()
        print(
            "========================================"
        )
        print(
            "DEBUG FINISHED"
        )
        print(
            "========================================"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()