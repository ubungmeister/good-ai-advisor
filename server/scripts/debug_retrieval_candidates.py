from app.db.database import SessionLocal
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_eval_loader import RetrievalEvalLoader


EVAL_FILE = "data/evals/retrieval_eval.json"

# We currently have ~124 chunks.
# 200 is intentionally larger so we can inspect
# the complete ranking for debugging.
FULL_SEARCH_LIMIT = 200

# Current production retrieval limits.
PRODUCTION_SEMANTIC_LIMIT = 20
PRODUCTION_LEXICAL_LIMIT = 20
PRODUCTION_RRF_LIMIT = 12

RRF_K = 20


DEBUG_CASES = {
    "baggage_theft_police_report": 37,
    "baggage_damage_repair": 38,
    "baggage_passport_exclusion": 39,
}


def get_article_number(chunk) -> int | None:
    """
    Read article number from DocumentChunk.
    """

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


def find_article_matches(
    results,
    expected_article: int,
):
    """
    Find every chunk belonging to the expected article.

    Returns:
        [
            (rank, chunk, score),
            ...
        ]
    """

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


def print_article_rank(
    stage_name: str,
    results,
    expected_article: int,
):
    """
    Print where expected article appears
    in a result list.
    """

    matches = find_article_matches(
        results=results,
        expected_article=expected_article,
    )

    if not matches:
        print(
            f"{stage_name}: "
            f"Article {expected_article} "
            f"-> NOT FOUND"
        )

        return

    print(
        f"{stage_name}: "
        f"Article {expected_article}"
    )

    for rank, chunk, score in matches:
        print(
            f"    rank={rank}, "
            f"score={score:.4f}, "
            f"chunk_id={chunk.id}"
        )


def print_top_results(
    stage_name: str,
    results,
    limit: int = 10,
):
    """
    Print first N results so we can see
    which articles are beating our expected one.
    """

    print()
    print(
        f"--- {stage_name} TOP {limit} ---"
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


def print_expected_chunk_content(
    results,
    expected_article: int,
):
    """
    Print text of chunks belonging to expected article.

    This helps us verify that the correct information
    is actually present inside the chunk.
    """

    matches = find_article_matches(
        results=results,
        expected_article=expected_article,
    )

    if not matches:
        print()
        print(
            "Expected article content: "
            "NOT AVAILABLE IN RESULTS"
        )

        return

    print()
    print(
        "--- EXPECTED ARTICLE CHUNK CONTENT ---"
    )

    for rank, chunk, score in matches:
        print()

        print(
            f"Article {expected_article}, "
            f"rank={rank}, "
            f"score={score:.4f}"
        )

        print(
            f"chunk_id={chunk.id}"
        )

        print()

        print(
            chunk.content
        )


def fuse_rrf(
    semantic_results,
    lexical_results,
):
    """
    Same basic Reciprocal Rank Fusion logic
    as our RetrievalService.

    IMPORTANT:
    This is only diagnostic code.

    It does not modify the production pipeline.
    """

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

        semantic_rank = (
            semantic_ranks.get(
                chunk_id
            )
        )

        lexical_rank = (
            lexical_ranks.get(
                chunk_id
            )
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


def main():

    loader = RetrievalEvalLoader()

    dataset = loader.load(
        EVAL_FILE
    )

    embedding_service = (
        EmbeddingService()
    )

    repository = (
        DocumentChunkRepository()
    )

    db = SessionLocal()

    try:

        print()
        print(
            "========================================"
        )
        print(
            "FULL RETRIEVAL CANDIDATE DEBUG"
        )
        print(
            "========================================"
        )

        for case in dataset.cases:

            if case.id not in DEBUG_CASES:
                continue

            expected_article = (
                DEBUG_CASES[case.id]
            )

            print()
            print()
            print(
                "=" * 70
            )

            print(
                f"CASE: {case.id}"
            )

            print(
                f"EXPECTED ARTICLE: "
                f"{expected_article}"
            )

            print(
                f"QUESTION: "
                f"{case.question}"
            )

            print(
                "=" * 70
            )

            # ==========================================
            # 1. Create query embedding
            # ==========================================

            query_embedding = (
                embedding_service.embed_query(
                    case.question
                )
            )

            # ==========================================
            # 2. FULL semantic search
            #
            # Production uses Top 20.
            #
            # Here we intentionally request much more
            # so we can see the real rank.
            # ==========================================

            semantic_results = list(
                repository.search_similar(
                    db=db,
                    embedding=query_embedding,
                    limit=FULL_SEARCH_LIMIT,
                )
            )

            print()
            print(
                "FULL SEMANTIC SEARCH"
            )

            print_article_rank(
                stage_name="Semantic full",
                results=semantic_results,
                expected_article=expected_article,
            )

            # ==========================================
            # 3. FULL lexical search
            # ==========================================

            lexical_results = list(
                repository.search_lexical(
                    db=db,
                    question=case.question,
                    limit=FULL_SEARCH_LIMIT,
                )
            )

            print()
            print(
                "FULL LEXICAL SEARCH"
            )

            print_article_rank(
                stage_name="Lexical full",
                results=lexical_results,
                expected_article=expected_article,
            )

            # ==========================================
            # 4. Check current production Top 20
            # ==========================================

            production_semantic = (
                semantic_results[
                    :PRODUCTION_SEMANTIC_LIMIT
                ]
            )

            production_lexical = (
                lexical_results[
                    :PRODUCTION_LEXICAL_LIMIT
                ]
            )

            print()
            print(
                "--- CURRENT PRODUCTION CUT-OFF ---"
            )

            print_article_rank(
                stage_name="Semantic Top 20",
                results=production_semantic,
                expected_article=expected_article,
            )

            print_article_rank(
                stage_name="Lexical Top 20",
                results=production_lexical,
                expected_article=expected_article,
            )

            # ==========================================
            # 5. Production RRF
            #
            # This reproduces the important part of
            # current production candidate generation:
            #
            # semantic Top 20
            # +
            # lexical Top 20
            # ->
            # RRF
            # ==========================================

            production_rrf = fuse_rrf(
                semantic_results=(
                    production_semantic
                ),
                lexical_results=(
                    production_lexical
                ),
            )

            print()
            print(
                "--- PRODUCTION RRF ---"
            )

            print_article_rank(
                stage_name="RRF full result",
                results=production_rrf,
                expected_article=expected_article,
            )

            production_candidates = (
                production_rrf[
                    :PRODUCTION_RRF_LIMIT
                ]
            )

            print_article_rank(
                stage_name="RRF Top 12",
                results=production_candidates,
                expected_article=expected_article,
            )

            # ==========================================
            # 6. Diagnostic FULL RRF
            #
            # IMPORTANT:
            # This is NOT production behaviour.
            #
            # We combine full rankings only to understand
            # what happens if both retrievers are allowed
            # to contribute without Top 20 truncation.
            # ==========================================

            full_rrf = fuse_rrf(
                semantic_results=semantic_results,
                lexical_results=lexical_results,
            )

            print()
            print(
                "--- DIAGNOSTIC FULL RRF ---"
            )

            print_article_rank(
                stage_name="Full RRF",
                results=full_rrf,
                expected_article=expected_article,
            )

            # ==========================================
            # 7. Show what beats the expected article
            # ==========================================

            print_top_results(
                stage_name="SEMANTIC",
                results=semantic_results,
                limit=10,
            )

            print_top_results(
                stage_name="LEXICAL",
                results=lexical_results,
                limit=10,
            )

            print_top_results(
                stage_name="PRODUCTION RRF",
                results=production_rrf,
                limit=12,
            )

            # ==========================================
            # 8. Show actual expected chunk text
            # ==========================================

            print_expected_chunk_content(
                results=semantic_results,
                expected_article=expected_article,
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