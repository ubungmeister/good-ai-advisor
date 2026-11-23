"""Compare three retrieval strategies on the same article-labelled questions.

Run from server/:
    python -m scripts.compare_retrieval --check
    python -m scripts.compare_retrieval --output data/evals/runs/retrieval-comparison.json

The evaluation is read-only and does not call any external LLM provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import time
from datetime import datetime, timezone
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/evals/retrieval_eval.json"
DEFAULT_OUTPUT = ROOT / "data/evals/runs/retrieval-comparison.json"
TOP_K = 10  # The existing run_retrieval_eval.py also evaluates 10 returned chunks.
VARIANTS = ("e5_only", "hybrid_rrf", "full_hybrid_reranker")


def load_cases(path: Path):
    """Use the repository's existing dataset validation rules."""
    from app.services.retrieval_eval_loader import RetrievalEvalLoader

    dataset = RetrievalEvalLoader().load(str(path))
    ids = [case.id for case in dataset.cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case IDs must be unique")
    return dataset


def expected_article_rank(results, *, document_id, expected_articles) -> int | None:
    """Replicate the document-scoped article matching used by run_retrieval_eval.py."""
    expected = set(expected_articles)
    for rank, (chunk, _score) in enumerate(results, start=1):
        if chunk.document_id != document_id:
            continue
        try:
            article = int(chunk.article_number)
        except (TypeError, ValueError):
            continue
        if article in expected:
            return rank
    return None


def article_list(results, *, document_id, limit=5) -> list[int | None]:
    """Return a lightweight inspection trail; no complete document text."""
    articles = []
    for chunk, _score in results[:limit]:
        if chunk.document_id != document_id:
            articles.append(None)
            continue
        try:
            articles.append(int(chunk.article_number))
        except (TypeError, ValueError):
            articles.append(None)
    return articles


def summarize(rows, key: str) -> dict:
    n = len(rows)
    ranks = [row["rank"][key] for row in rows]
    durations = [row["estimated_latency_seconds"][key] for row in rows]
    sorted_times = sorted(durations)
    return {
        "questions": n,
        "hit_at_1": sum(r is not None and r <= 1 for r in ranks) / n,
        "hit_at_3": sum(r is not None and r <= 3 for r in ranks) / n,
        "hit_at_5": sum(r is not None and r <= 5 for r in ranks) / n,
        "mrr_at_10": sum(1.0 / r for r in ranks if r is not None) / n,
        "mean_estimated_seconds": statistics.mean(durations),
        "median_estimated_seconds": statistics.median(durations),
        "p95_estimated_seconds": sorted_times[math.ceil(0.95 * n) - 1],
        "misses_in_top_5": [row["id"] for row in rows if row["rank"][key] is None or row["rank"][key] > 5],
    }


def git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def evaluate(dataset, *, dataset_path: Path, product_version_id: UUID | None, output: Path):
    from app.db.database import SessionLocal
    from app.services.retrieval_service import RetrievalService
    from scripts.retrieval_scope import resolve_document_scope

    rows = []
    # Model loading is a cold-start cost and deliberately excluded from these timings.
    model_load_start = time.perf_counter()
    service = RetrievalService()
    model_load_seconds = time.perf_counter() - model_load_start

    with SessionLocal() as db:
        # PostgreSQL read-only transaction: this script should never modify demo data.
        db.connection().exec_driver_sql("SET TRANSACTION READ ONLY")
        document = resolve_document_scope(db, dataset.document_code, product_version_id)
        version_id = document.product_version_id
        doc_id = document.id

        for index, case in enumerate(dataset.cases, 1):
            question = case.question
            stage = {}

            t = time.perf_counter()
            embedding = service.embedding_service.embed_query(question)
            stage["embedding"] = time.perf_counter() - t

            t = time.perf_counter()
            semantic = list(service.document_chunk_repository.search_similar(
                db=db, embedding=embedding, limit=service.SEMANTIC_LIMIT,
                product_version_id=version_id,
            ))
            stage["semantic_search"] = time.perf_counter() - t

            t = time.perf_counter()
            original = list(service.document_chunk_repository.search_lexical(
                db=db, question=question, limit=service.ORIGINAL_LEXICAL_LIMIT,
                product_version_id=version_id,
            ))
            stage["original_lexical_search"] = time.perf_counter() - t

            t = time.perf_counter()
            expanded_query = service.lexical_query_builder.build(question)
            stage["stanza_query_builder"] = time.perf_counter() - t

            t = time.perf_counter()
            expanded = list(service.document_chunk_repository.search_lexical(
                db=db, question=expanded_query, limit=service.STANZA_LEXICAL_LIMIT,
                product_version_id=version_id,
            ))
            stage["stanza_lexical_search"] = time.perf_counter() - t

            t = time.perf_counter()
            fused = service._fuse_retrieval_results(
                result_lists=[semantic, original, expanded],
            )
            stage["rrf_fusion"] = time.perf_counter() - t

            t = time.perf_counter()
            protected_candidates = service._build_protected_candidates(
                semantic_results=semantic,
                original_lexical_results=original,
                stanza_lexical_results=expanded,
                fused_results=fused,
            )
            stage["protected_candidate_selection"] = time.perf_counter() - t

            t = time.perf_counter()
            reranked = service.reranker_service.rerank(
                question=question,
                candidates=protected_candidates,
                limit=service.RERANKER_CANDIDATE_LIMIT,
            )
            stage["cross_encoder_reranking"] = time.perf_counter() - t

            ranked = {
                "e5_only": semantic[:TOP_K],
                "hybrid_rrf": fused[:TOP_K],
                "full_hybrid_reranker": reranked[:TOP_K],
            }
            e5_time = stage["embedding"] + stage["semantic_search"]
            hybrid_time = e5_time + sum(stage[name] for name in (
                "original_lexical_search", "stanza_query_builder", "stanza_lexical_search", "rrf_fusion",
            ))
            estimated_times = {
                "e5_only": e5_time,
                "hybrid_rrf": hybrid_time,
                "full_hybrid_reranker": hybrid_time + stage["protected_candidate_selection"] + stage["cross_encoder_reranking"],
            }

            row = {
                "id": case.id,
                "category": case.category,
                "question": question,
                "expected_articles": case.expected_articles,
                "rank": {
                    name: expected_article_rank(results, document_id=doc_id, expected_articles=case.expected_articles)
                    for name, results in ranked.items()
                },
                "top_5_articles": {
                    name: article_list(results, document_id=doc_id)
                    for name, results in ranked.items()
                },
                "estimated_latency_seconds": {
                    name: round(seconds, 6) for name, seconds in estimated_times.items()
                },
                "stage_seconds": {name: round(seconds, 6) for name, seconds in stage.items()},
                "reranker_candidates": len(protected_candidates),
            }
            rows.append(row)
            print(
                f"[{index:02d}/{len(dataset.cases):02d}] {case.id}: "
                + ", ".join(f"{name}={row['rank'][name] or '-'}" for name in VARIANTS),
                flush=True,
            )

        metadata = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_head(),
            "document_code": dataset.document_code,
            "document_id": str(doc_id),
            "product_version_id": str(version_id),
            "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
            "question_count": len(dataset.cases),
            "evaluation_top_k": TOP_K,
            "rrf_k": service.RRF_K,
            "candidate_limit": service.RERANKER_CANDIDATE_LIMIT,
            "model_initialization_seconds": round(model_load_seconds, 4),
            "method": (
                "For each question, the exact same semantic and two lexical rankings are reused "
                "to evaluate E5-only, hybrid RRF, and the current protected-candidate + reranker path. "
                "Article correctness is document-scoped and matches any expected article."
            ),
            "latency_note": (
                "Estimated marginal warm-query timings calculated from shared stages, "
                "not independently timed end-to-end requests. Excludes model initialization, "
                "chat, LLM calls, UI and network overhead."
            ),
        }
        report = {
            "metadata": metadata,
            "summary": {key: summarize(rows, key) for key in VARIANTS},
            "cases": rows,
        }
        # The existing evaluation scripts write local results to Git-ignored data/evals/runs.
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
        db.rollback()

    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--product-version-id", type=UUID)
    parser.add_argument("--check", action="store_true", help="Check case IDs and dataset without database or models")
    args = parser.parse_args()

    dataset = load_cases(args.dataset)
    if args.check:
        print(f"PASS: {len(dataset.cases)} unique article-labelled cases in {args.dataset}")
        return
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}; choose a new --output path")

    report = evaluate(
        dataset, dataset_path=args.dataset,
        product_version_id=args.product_version_id, output=args.output,
    )
    print("\nRETRIEVAL COMPARISON (same 26 reference questions)")
    print(f"{'Variant':<24} {'Hit@1':>8} {'Hit@3':>8} {'Hit@5':>8} {'MRR@10':>9} {'Mean (s)*':>11}")
    for name in VARIANTS:
        m = report["summary"][name]
        print(f"{name:<24} {m['hit_at_1'] * 100:>7.1f}% {m['hit_at_3'] * 100:>7.1f}% "
              f"{m['hit_at_5'] * 100:>7.1f}% {m['mrr_at_10']:>9.3f} {m['mean_estimated_seconds']:>11.3f}")
    print("*Stage-derived approximate warm-query time, not independent latency runs.")
    print(f"Full report: {args.output}")


if __name__ == "__main__":
    main()
