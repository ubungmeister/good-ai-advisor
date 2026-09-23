from app.db.database import SessionLocal
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.services.embedding_service import EmbeddingService


SEMANTIC_LIMIT = 20
LEXICAL_LIMIT = 20
RRF_CANDIDATE_LIMIT = 12

RRF_K = 20


TEST_CASES = [
    {
        "id": "baggage_theft_police_report",
        "expected_article": 37,
        "question": (
            "Musím krádež zavazadla v zahraničí "
            "nahlásit policii a doložit policejní protokol?"
        ),
        "lexical_query": (
            "krádež zavazadla policii policejní protokol"
        ),
    },
    {
        "id": "baggage_damage_repair",
        "expected_article": 38,
        "question": (
            "Jak pojišťovna postupuje, když se moje "
            "zavazadlo poškodí a je možné ho opravit?"
        ),
        "lexical_query": (
            "poškození zavazadla oprava"
        ),
    },
    {
        "id": "baggage_passport_exclusion",
        "expected_article": 39,
        "question": (
            "Je cestovní pas pojištěný v rámci "
            "pojištění zavazadel?"
        ),
        "lexical_query": (
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


def find_article_rank(
    results,
    expected_article: int,
):
    for rank, (
        chunk,
        score,
    ) in enumerate(
        results,
        start=1,
    ):
        if (
            get_article_number(chunk)
            == expected_article
        ):
            return rank, score

    return None, None


def print_article_rank(
    label: str,
    results,
    expected_article: int,
):
    rank, score = find_article_rank(
        results=results,
        expected_article=expected_article,
    )

    if rank is None:
        print(
            f"{label}: "
            f"Article {expected_article} -> NOT FOUND"
        )

        return

    print(
        f"{label}: "
        f"Article {expected_article} "
        f"-> rank={rank}, "
        f"score={score:.4f}"
    )


def fuse_rrf(
    semantic_results,
    lexical_results,
):
    semantic_ranks = {
        chunk.id: rank
        for rank, (
            chunk,
            _,
        ) in enumerate(
            semantic_results,
            start=1,
        )
    }

    lexical_ranks = {
        chunk.id: rank
        for rank, (
            chunk,
            _,
        ) in enumerate(
            lexical_results,
            start=1,
        )
    }

    chunks_by_id = {}

    for chunk, _ in semantic_results:
        chunks_by_id[chunk.id] = chunk

    for chunk, _ in lexical_results:
        chunks_by_id[chunk.id] = chunk

    fused_results = []

    for chunk_id, chunk in chunks_by_id.items():

        score = 0.0

        semantic_rank = semantic_ranks.get(
            chunk_id
        )

        lexical_rank = lexical_ranks.get(
            chunk_id
        )

        if semantic_rank is not None:
            score += (
                1.0
                / (
                    RRF_K
                    + semantic_rank
                )
            )

        if lexical_rank is not None:
            score += (
                1.0
                / (
                    RRF_K
                    + lexical_rank
                )
            )

        fused_results.append(
            (
                chunk,
                score,
            )
        )

    fused_results.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    return fused_results


def print_top_results(
    label: str,
    results,
    limit: int,
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
        article_number = (
            get_article_number(chunk)
        )

        print(
            f"#{rank:02d} "
            f"Article {article_number} "
            f"score={score:.4f}"
        )


def main():
    embedding_service = EmbeddingService()

    repository = DocumentChunkRepository()

    db = SessionLocal()

    try:
        print()
        print(
            "========================================"
        )
        print(
            "FOCUSED HYBRID RETRIEVAL DEBUG"
        )
        print(
            "========================================"
        )

        for case in TEST_CASES:

            expected_article = (
                case["expected_article"]
            )

            question = case["question"]

            lexical_query = (
                case["lexical_query"]
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
                f"QUESTION: "
                f"{question}"
            )

            print(
                f"LEXICAL QUERY: "
                f"{lexical_query}"
            )

            print(
                "=" * 70
            )

            # ==========================================
            # Semantic retrieval
            #
            # IMPORTANT:
            # Semantic search still receives the
            # ORIGINAL user question.
            # ==========================================

            query_embedding = (
                embedding_service.embed_query(
                    question
                )
            )

            semantic_results = list(
                repository.search_similar(
                    db=db,
                    embedding=query_embedding,
                    limit=SEMANTIC_LIMIT,
                )
            )

            # ==========================================
            # Lexical retrieval
            #
            # Only lexical search receives the
            # focused query.
            # ==========================================

            lexical_results = list(
                repository.search_lexical(
                    db=db,
                    question=lexical_query,
                    limit=LEXICAL_LIMIT,
                )
            )

            print()
            print_article_rank(
                label="Semantic Top 20",
                results=semantic_results,
                expected_article=expected_article,
            )

            print_article_rank(
                label="Focused lexical Top 20",
                results=lexical_results,
                expected_article=expected_article,
            )

            # ==========================================
            # RRF
            # ==========================================

            fused_results = fuse_rrf(
                semantic_results=semantic_results,
                lexical_results=lexical_results,
            )

            print_article_rank(
                label="RRF full",
                results=fused_results,
                expected_article=expected_article,
            )

            # ==========================================
            # Production candidate cut-off
            # ==========================================

            candidates = fused_results[
                :RRF_CANDIDATE_LIMIT
            ]

            print_article_rank(
                label="RRF Top 12",
                results=candidates,
                expected_article=expected_article,
            )

            print_top_results(
                label="RRF",
                results=fused_results,
                limit=12,
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