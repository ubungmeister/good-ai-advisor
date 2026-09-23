from app.db.database import SessionLocal
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.services.lexical_query_builder import (
    LexicalQueryBuilder,
)
from app.services.retrieval_eval_loader import (
    RetrievalEvalLoader,
)


EVAL_FILE = "data/evals/retrieval_eval.json"

# Large enough so we can see the real lexical rank
# of the expected article.
SEARCH_LIMIT = 200


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


def find_expected_rank(
    results,
    expected_articles: list[int],
) -> int | None:
    """
    Return the first rank containing one of the
    expected articles.
    """

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

        if article_number in expected_articles:
            return rank

    return None


def rank_label(
    rank: int | None,
) -> str:
    if rank is None:
        return "NOT FOUND"

    return f"#{rank}"


def main():
    loader = RetrievalEvalLoader()

    dataset = loader.load(
        EVAL_FILE
    )

    repository = (
        DocumentChunkRepository()
    )

    query_builder = (
        LexicalQueryBuilder()
    )

    db = SessionLocal()

    improved = 0
    same = 0
    worse = 0

    original_top_20_hits = 0
    stanza_top_20_hits = 0

    original_reciprocal_rank_sum = 0.0
    stanza_reciprocal_rank_sum = 0.0

    executed_cases = 0

    try:
        print()
        print(
            "========================================"
        )
        print(
            "LEXICAL BUILDER FULL EVAL"
        )
        print(
            "========================================"
        )
        print()

        for case in dataset.cases:
            executed_cases += 1

            # ==========================================
            # Current lexical query:
            # full natural-language question
            # ==========================================

            original_results = list(
                repository.search_lexical(
                    db=db,
                    question=case.question,
                    limit=SEARCH_LIMIT,
                )
            )

            original_rank = find_expected_rank(
                results=original_results,
                expected_articles=case.expected_articles,
            )

            # ==========================================
            # New lexical query:
            # Stanza lemma + POS + noise filtering
            # ==========================================

            lexical_query = (
                query_builder.build(
                    case.question
                )
            )

            stanza_results = list(
                repository.search_lexical(
                    db=db,
                    question=lexical_query,
                    limit=SEARCH_LIMIT,
                )
            )

            stanza_rank = find_expected_rank(
                results=stanza_results,
                expected_articles=case.expected_articles,
            )

            # ==========================================
            # Compare
            # ==========================================

            if (
                original_rank is None
                and stanza_rank is not None
            ):
                status = "IMPROVED"
                improved += 1

            elif (
                original_rank is not None
                and stanza_rank is None
            ):
                status = "WORSE"
                worse += 1

            elif (
                original_rank is None
                and stanza_rank is None
            ):
                status = "SAME"
                same += 1

            elif stanza_rank < original_rank:
                status = "IMPROVED"
                improved += 1

            elif stanza_rank > original_rank:
                status = "WORSE"
                worse += 1

            else:
                status = "SAME"
                same += 1

            # ==========================================
            # Top 20 recall
            #
            # Production lexical search currently
            # keeps only Top 20.
            # ==========================================

            if (
                original_rank is not None
                and original_rank <= 20
            ):
                original_top_20_hits += 1

            if (
                stanza_rank is not None
                and stanza_rank <= 20
            ):
                stanza_top_20_hits += 1

            # ==========================================
            # Lexical-only MRR
            #
            # This is NOT our final RAG MRR.
            #
            # It is useful only for comparing lexical
            # ranking before vs after preprocessing.
            # ==========================================

            if original_rank is not None:
                original_reciprocal_rank_sum += (
                    1 / original_rank
                )

            if stanza_rank is not None:
                stanza_reciprocal_rank_sum += (
                    1 / stanza_rank
                )

            # ==========================================
            # Output per case
            # ==========================================

            print(
                f"{case.id}"
            )

            print(
                f"  expected: "
                f"{case.expected_articles}"
            )

            print(
                f"  original query:"
            )

            print(
                f"    {case.question}"
            )

            print(
                f"  stanza query:"
            )

            print(
                f"    {lexical_query}"
            )

            print(
                f"  original rank: "
                f"{rank_label(original_rank)}"
            )

            print(
                f"  stanza rank:   "
                f"{rank_label(stanza_rank)}"
            )

            print(
                f"  result:        "
                f"{status}"
            )

            print()

        # ==============================================
        # Final summary
        # ==============================================

        total = executed_cases

        print()
        print(
            "========================================"
        )
        print(
            "SUMMARY"
        )
        print(
            "========================================"
        )
        print()

        print(
            f"Queries: {total}"
        )

        print()
        print(
            "Rank comparison:"
        )

        print(
            f"  Improved: {improved}"
        )

        print(
            f"  Same:     {same}"
        )

        print(
            f"  Worse:    {worse}"
        )

        print()
        print(
            "Top 20 recall:"
        )

        print(
            f"  Original: "
            f"{original_top_20_hits}/{total} "
            f"({original_top_20_hits / total:.2%})"
        )

        print(
            f"  Stanza:   "
            f"{stanza_top_20_hits}/{total} "
            f"({stanza_top_20_hits / total:.2%})"
        )

        original_mrr = (
            original_reciprocal_rank_sum
            / total
        )

        stanza_mrr = (
            stanza_reciprocal_rank_sum
            / total
        )

        print()
        print(
            "Lexical-only MRR:"
        )

        print(
            f"  Original: "
            f"{original_mrr:.3f}"
        )

        print(
            f"  Stanza:   "
            f"{stanza_mrr:.3f}"
        )

        print()

    finally:
        db.close()


if __name__ == "__main__":
    main()