"""Read-only stage-by-stage retrieval diagnosis for the existing reference cases."""

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]


class RecordingRepository:
    def __init__(self, target, stages):
        self.target, self.stages = target, stages

    def search_similar(self, **kwargs):
        rows = list(self.target.search_similar(**kwargs))
        self.stages["semantic"] = rows
        return rows

    def search_lexical(self, **kwargs):
        rows = list(self.target.search_lexical(**kwargs))
        stage = "lexical_original" if "lexical_original" not in self.stages else "lexical_expanded"
        self.stages[stage] = rows
        return rows


class RecordingReranker:
    def __init__(self, target, stages):
        self.target, self.stages = target, stages

    def rerank(self, **kwargs):
        self.stages["candidates"] = kwargs["candidates"]
        rows = self.target.rerank(**kwargs)
        self.stages["reranked"] = rows
        return rows


def main():
    from app.db.database import SessionLocal
    from app.services.retrieval_service import RetrievalService
    from scripts.retrieval_scope import resolve_document_scope
    from scripts.run_ai_eval import load_dataset, DEFAULT_DATASET

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--product-version-id", type=UUID)
    parser.add_argument("--chat-report", type=Path, help="Include the actual planner queries from a chat run")
    parser.add_argument("--only-chat-report", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output path; existing reports are preserved")
    dataset = json.loads((ROOT / "data/evals/retrieval_eval.json").read_text(encoding="utf-8"))
    cases = list(dataset["cases"])
    cases += [{"id": c.id, "question": c.question, "expected_articles": c.articles}
              for c in load_dataset(DEFAULT_DATASET).cases if c.suite == "chat" and c.articles]
    if args.only_chat_report:
        if not args.chat_report:
            parser.error("--only-chat-report requires --chat-report")
        cases = []
    if args.chat_report:
        gold = {case.id: case for case in load_dataset(DEFAULT_DATASET).cases if case.articles}
        report = json.loads(args.chat_report.read_text(encoding="utf-8-sig"))
        for row in report["results"]:
            if row["id"] not in gold or not row.get("turns"):
                continue
            for call in row["turns"][-1]["trace"]["planner"]:
                for index, task in enumerate(call.get("output", {}).get("tasks", [])):
                    cases.append({"id": f"{row['id']}_planned_{index}", "question": task["query"],
                                  "expected_articles": gold[row["id"]].articles})
    stages = {}
    results = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        db.connection().exec_driver_sql("SET TRANSACTION READ ONLY")
        document = resolve_document_scope(db, dataset["document_code"], args.product_version_id)
        service = RetrievalService()
        service.document_chunk_repository = RecordingRepository(service.document_chunk_repository, stages)
        service.reranker_service = RecordingReranker(service.reranker_service, stages)
        for case in cases:
            stages.clear()
            with redirect_stdout(io.StringIO()):
                final = service.search(db=db, question=case["question"], limit=5,
                                       product_version_id=document.product_version_id)
            stages["final"] = final
            stage_rows = {name: [{"id": str(chunk.id), "document_id": str(chunk.document_id),
                                  "article": str(chunk.article_number), "score": float(score)}
                                 for chunk, score in rows] for name, rows in stages.items()}
            ranks = {name: next((rank for rank, row in enumerate(rows, 1)
                                 if row["document_id"] == str(document.id)
                                 and row["article"] in {str(n) for n in case["expected_articles"]}), None)
                     for name, rows in stage_rows.items()}
            results.append({**case, "ranks": ranks, "stages": stage_rows})
            args.output.write_text(json.dumps({"document_id": str(document.id),
                "product_version_id": str(document.product_version_id), "results": results},
                ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{case['id']}: {ranks}", flush=True)
        db.rollback()


if __name__ == "__main__":
    main()
