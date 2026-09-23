from app.db.database import SessionLocal
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.services.embedding_service import EmbeddingService
from app.services.lexical_query_builder import (
    LexicalQueryBuilder,
)
from app.services.reranker_service import RerankerService
from app.services.retrieval_eval_loader import (
    RetrievalEvalLoader,
)


EVAL_FILE = "data/evals/retrieval_eval.json"

TARGET_CASES = {
    "assistance_vaccination_info",
    "baggage_theft_police_report",
}

# Large limits only for diagnostics:
# we want to know the REAL rank.
DEBUG_LIMIT = 200

# Production limits.
SEMANTIC_LIMIT = 20
LEXICAL_LIMIT = 20

SEMANTIC_PROTECTED = 5
ORIGINAL_LEXICAL_PROTECTED = 3
STANZA_LEXICAL_PROTECTED = 5
RERANKER_CANDIDATE_LIMIT = 12

RRF_K = 20


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
    expected_articles,
) -> int | None:
    for rank, (chunk, _) in enumerate(
        results,
        start=1,
    ):
        article = get_article_number(chunk)

        if article in expected_articles:
            return rank

    return None


def fuse_rrf(
    result_lists,
):
    scores = {}
    chunks_by_id = {}

    for results in result_lists:

        for rank, (chunk, _) in enumerate(
            results,
            start=1,
        ):
            chunks_by_id[chunk.id] = chunk

            scores.setdefault(
                chunk.id,
                0.0,
            )

            scores[chunk.id] += (
                1.0
                / (
                    RRF_K
                    + rank
                )
            )

    fused = [
        (
            chunks_by_id[chunk_id],
            score,
        )
        for chunk_id, score
        in scores.items()
    ]

    fused.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    return fused


def build_protected_candidates(
    semantic_results,
    original_lexical_results,
    stanza_lexical_results,
    fused_results,
):
    selected = []
    selected_ids = set()

    def add(chunk):
        if chunk.id in selected_ids:
            return

        if len(selected) >= RERANKER_CANDIDATE_LIMIT:
            return

        selected.append(chunk)
        selected_ids.add(chunk.id)

    # Protect strongest candidates from all 3 branches.
    for chunk, _ in semantic_results[
        :SEMANTIC_PROTECTED
    ]:
        add(chunk)

    for chunk, _ in original_lexical_results[
        :ORIGINAL_LEXICAL_PROTECTED
    ]:
        add(chunk)

    for chunk, _ in stanza_lexical_results[
        :STANZA_LEXICAL_PROTECTED
    ]:
        add(chunk)

    # Fill remaining positions from RRF.
    for chunk, _ in fused_results:
        if (
            len(selected)
            >= RERANKER_CANDIDATE_LIMIT
        ):
            break

        add(chunk)

    rrf_scores = {
        chunk.id: score
        for chunk, score in fused_results
    }

    return [
        (
            chunk,
            rrf_scores.get(
                chunk.id,
                0.0,
            ),
        )
        for chunk in selected
    ]


def print_stage(
    name,
    results,
    expected_articles,
):
    rank = find_article_rank(
        results,
        expected_articles,
    )

    print(
        f"{name:<28}: "
        f"{rank if rank is not None else 'NONE'}"
    )

    return rank


def print_candidate_articles(
    title,
    results,
):
    print()
    print(title)

    for rank, (chunk, score) in enumerate(
        results,
        start=1,
    ):
        article = get_article_number(chunk)

        print(
            f"  #{rank:02d} "
            f"Article {article} "
            f"score={score:.4f}"
        )


def main():
    loader = RetrievalEvalLoader()

    dataset = loader.load(
        EVAL_FILE
    )

    repository = (
        DocumentChunkRepository()
    )

    embedding_service = (
        EmbeddingService()
    )

    lexical_builder = (
        LexicalQueryBuilder()
    )

    reranker = (
        RerankerService()
    )

    db = SessionLocal()

    try:

        print()
        print(
            "========================================"
        )
        print(
            "REMAINING MISSES DIAGNOSTIC"
        )
        print(
            "========================================"
        )

        for case in dataset.cases:

            if case.id not in TARGET_CASES:
                continue

            print()
            print()
            print(
                "=" * 70
            )

            print(
                f"CASE: {case.id}"
            )

            print(
                f"EXPECTED: "
                f"{case.expected_articles}"
            )

            print(
                f"QUESTION:"
            )

            print(
                case.question
            )

            # ==========================================
            # E5 semantic
            # ==========================================

            embedding = (
                embedding_service.embed_query(
                    case.question
                )
            )

            semantic_full = list(
                repository.search_similar(
                    db=db,
                    embedding=embedding,
                    limit=DEBUG_LIMIT,
                )
            )

            semantic_prod = (
                semantic_full[
                    :SEMANTIC_LIMIT
                ]
            )

            # ==========================================
            # Original lexical
            # ==========================================

            original_full = list(
                repository.search_lexical(
                    db=db,
                    question=case.question,
                    limit=DEBUG_LIMIT,
                )
            )

            original_prod = (
                original_full[
                    :LEXICAL_LIMIT
                ]
            )

            # ==========================================
            # Stanza lexical
            # ==========================================

            stanza_query = (
                lexical_builder.build(
                    case.question
                )
            )

            stanza_full = list(
                repository.search_lexical(
                    db=db,
                    question=stanza_query,
                    limit=DEBUG_LIMIT,
                )
            )

            stanza_prod = (
                stanza_full[
                    :LEXICAL_LIMIT
                ]
            )

            print()
            print(
                f"STANZA QUERY:"
            )

            print(
                stanza_query
            )

            print()
            print(
                "--- FULL RETRIEVER RANKS ---"
            )

            print_stage(
                "Semantic full",
                semantic_full,
                case.expected_articles,
            )

            print_stage(
                "Original lexical full",
                original_full,
                case.expected_articles,
            )

            print_stage(
                "Stanza lexical full",
                stanza_full,
                case.expected_articles,
            )

            print()
            print(
                "--- PRODUCTION TOP20 ---"
            )

            print_stage(
                "Semantic Top20",
                semantic_prod,
                case.expected_articles,
            )

            print_stage(
                "Original lexical Top20",
                original_prod,
                case.expected_articles,
            )

            print_stage(
                "Stanza lexical Top20",
                stanza_prod,
                case.expected_articles,
            )

            # ==========================================
            # RRF
            # ==========================================

            fused = fuse_rrf(
                [
                    semantic_prod,
                    original_prod,
                    stanza_prod,
                ]
            )

            print()
            print(
                "--- RRF ---"
            )

            print_stage(
                "RRF full",
                fused,
                case.expected_articles,
            )

            print_stage(
                "RRF Top12",
                fused[
                    :RERANKER_CANDIDATE_LIMIT
                ],
                case.expected_articles,
            )

            # ==========================================
            # Protected candidates
            # ==========================================

            protected = (
                build_protected_candidates(
                    semantic_results=(
                        semantic_prod
                    ),
                    original_lexical_results=(
                        original_prod
                    ),
                    stanza_lexical_results=(
                        stanza_prod
                    ),
                    fused_results=fused,
                )
            )

            print()
            print(
                "--- PROTECTED CANDIDATES ---"
            )

            protected_rank = (
                print_stage(
                    "Protected Top12",
                    protected,
                    case.expected_articles,
                )
            )

            print_candidate_articles(
                "Protected candidate articles:",
                protected,
            )

            # ==========================================
            # Reranker
            # ==========================================

            reranked = reranker.rerank(
                question=case.question,
                candidates=protected,
                limit=RERANKER_CANDIDATE_LIMIT,
            )

            print()
            print(
                "--- RERANKER ---"
            )

            reranker_rank = (
                print_stage(
                    "Reranker Top12",
                    reranked,
                    case.expected_articles,
                )
            )

            final_results = (
                reranked[:5]
            )

            final_rank = (
                print_stage(
                    "Final Top5",
                    final_results,
                    case.expected_articles,
                )
            )

            print_candidate_articles(
                "Reranked articles:",
                reranked,
            )

            # ==========================================
            # Simple diagnosis
            # ==========================================

            print()
            print(
                "--- DIAGNOSIS ---"
            )

            if protected_rank is None:
                print(
                    "Expected article is lost BEFORE "
                    "the reranker."
                )

            elif reranker_rank is None:
                print(
                    "Unexpected: expected article was "
                    "candidate but disappeared completely."
                )

            elif final_rank is None:
                print(
                    "Expected article reaches reranker, "
                    "but reranker puts it below Top5."
                )

            else:
                print(
                    "Expected article reaches Final Top5."
                )

    finally:
        db.close()


if __name__ == "__main__":
    main()