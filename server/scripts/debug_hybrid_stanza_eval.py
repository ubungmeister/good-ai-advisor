import time

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

SEMANTIC_LIMIT = 20
LEXICAL_LIMIT = 20
RERANKER_CANDIDATE_LIMIT = 12
FINAL_LIMIT = 5

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


def find_expected_rank(
    results,
    expected_articles: list[int],
) -> int | None:

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


def update_metrics(
    rank: int | None,
    metrics: dict,
):
    if rank is None:
        return

    if rank <= 1:
        metrics["hit_1"] += 1

    if rank <= 3:
        metrics["hit_3"] += 1

    if rank <= 5:
        metrics["hit_5"] += 1

    metrics["rr_sum"] += (
        1 / rank
    )


def print_metrics(
    label: str,
    metrics: dict,
    total: int,
):
    print()
    print(label)

    print(
        f"  Hit@1: "
        f"{metrics['hit_1'] / total:.2%}"
    )

    print(
        f"  Hit@3: "
        f"{metrics['hit_3'] / total:.2%}"
    )

    print(
        f"  Hit@5: "
        f"{metrics['hit_5'] / total:.2%}"
    )

    print(
        f"  MRR: "
        f"{metrics['rr_sum'] / total:.3f}"
    )

    print(
        f"  Avg latency: "
        f"{metrics['latency_sum'] / total:.3f} sec"
    )


def run_pipeline_variant(
    question: str,
    lexical_query: str,
    semantic_results,
    repository,
    reranker,
    db,
    shared_time: float,
):
    """
    Runs one hybrid variant.

    Semantic retrieval is shared between A/B because
    it is identical in both variants.

    shared_time contains:
    - embedding
    - semantic search

    We add that same cost to both variants so latency
    remains comparable.
    """

    variant_start = time.perf_counter()

    # ==========================================
    # Lexical search
    # ==========================================

    lexical_results = list(
        repository.search_lexical(
            db=db,
            question=lexical_query,
            limit=LEXICAL_LIMIT,
        )
    )

    # ==========================================
    # RRF
    # ==========================================

    fused_results = fuse_rrf(
        semantic_results=semantic_results,
        lexical_results=lexical_results,
    )

    candidates = fused_results[
        :RERANKER_CANDIDATE_LIMIT
    ]

    # ==========================================
    # Reranker
    # ==========================================

    reranked = reranker.rerank(
        question=question,
        candidates=candidates,
        limit=RERANKER_CANDIDATE_LIMIT,
    )

    final_results = reranked[
        :FINAL_LIMIT
    ]

    variant_time = (
        time.perf_counter()
        - variant_start
    )

    estimated_full_time = (
        shared_time
        + variant_time
    )

    return (
        final_results,
        estimated_full_time,
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

    lexical_query_builder = (
        LexicalQueryBuilder()
    )

    reranker = (
        RerankerService()
    )

    db = SessionLocal()

    current_metrics = {
        "hit_1": 0,
        "hit_3": 0,
        "hit_5": 0,
        "rr_sum": 0.0,
        "latency_sum": 0.0,
    }

    stanza_metrics = {
        "hit_1": 0,
        "hit_3": 0,
        "hit_5": 0,
        "rr_sum": 0.0,
        "latency_sum": 0.0,
    }

    improved = 0
    same = 0
    worse = 0

    total = 0

    try:
        print()
        print(
            "========================================"
        )
        print(
            "HYBRID STANZA A/B EVAL"
        )
        print(
            "========================================"
        )
        print()

        for case in dataset.cases:

            total += 1

            question = case.question

            # ==========================================
            # Shared semantic stage
            # ==========================================

            shared_start = (
                time.perf_counter()
            )

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

            shared_time = (
                time.perf_counter()
                - shared_start
            )

            # ==========================================
            # Variant A
            #
            # CURRENT:
            # full user question goes directly
            # to lexical search.
            # ==========================================

            (
                current_results,
                current_time,
            ) = run_pipeline_variant(
                question=question,
                lexical_query=question,
                semantic_results=semantic_results,
                repository=repository,
                reranker=reranker,
                db=db,
                shared_time=shared_time,
            )

            current_rank = (
                find_expected_rank(
                    results=current_results,
                    expected_articles=(
                        case.expected_articles
                    ),
                )
            )

            # ==========================================
            # Variant B
            #
            # STANZA:
            # user question -> LexicalQueryBuilder
            # -> lexical search.
            # ==========================================

            stanza_query = (
                lexical_query_builder.build(
                    question
                )
            )

            (
                stanza_results,
                stanza_time,
            ) = run_pipeline_variant(
                question=question,
                lexical_query=stanza_query,
                semantic_results=semantic_results,
                repository=repository,
                reranker=reranker,
                db=db,
                shared_time=shared_time,
            )

            stanza_rank = (
                find_expected_rank(
                    results=stanza_results,
                    expected_articles=(
                        case.expected_articles
                    ),
                )
            )

            # ==========================================
            # Metrics
            # ==========================================

            update_metrics(
                rank=current_rank,
                metrics=current_metrics,
            )

            update_metrics(
                rank=stanza_rank,
                metrics=stanza_metrics,
            )

            current_metrics[
                "latency_sum"
            ] += current_time

            stanza_metrics[
                "latency_sum"
            ] += stanza_time

            # ==========================================
            # Compare final result
            # ==========================================

            if (
                current_rank is None
                and stanza_rank is not None
            ):
                status = "IMPROVED"
                improved += 1

            elif (
                current_rank is not None
                and stanza_rank is None
            ):
                status = "WORSE"
                worse += 1

            elif (
                current_rank is None
                and stanza_rank is None
            ):
                status = "SAME"
                same += 1

            elif stanza_rank < current_rank:
                status = "IMPROVED"
                improved += 1

            elif stanza_rank > current_rank:
                status = "WORSE"
                worse += 1

            else:
                status = "SAME"
                same += 1

            # ==========================================
            # Output
            # ==========================================

            print(case.id)

            print(
                f"  expected: "
                f"{case.expected_articles}"
            )

            print(
                f"  stanza query:"
            )

            print(
                f"    {stanza_query}"
            )

            print(
                f"  current final rank: "
                f"{current_rank}"
            )

            print(
                f"  stanza final rank:  "
                f"{stanza_rank}"
            )

            print(
                f"  result: "
                f"{status}"
            )

            print(
                f"  current latency: "
                f"{current_time:.3f}s"
            )

            print(
                f"  stanza latency:  "
                f"{stanza_time:.3f}s"
            )

            print()

        # ==============================================
        # SUMMARY
        # ==============================================

        print()
        print(
            "========================================"
        )
        print(
            "FINAL A/B RESULTS"
        )
        print(
            "========================================"
        )

        print(
            f"Queries: {total}"
        )

        print_metrics(
            label="CURRENT PIPELINE",
            metrics=current_metrics,
            total=total,
        )

        print_metrics(
            label="STANZA PIPELINE",
            metrics=stanza_metrics,
            total=total,
        )

        print()
        print(
            "Per-case comparison:"
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

    finally:
        db.close()


if __name__ == "__main__":
    main()