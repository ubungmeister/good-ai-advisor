"""Evaluate real chat orchestration and validators against versioned reference cases."""

import argparse
import asyncio
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import time
from uuid import UUID

from app.schemas.ai_eval import EvalDataset

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data/evals/ai_eval.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_dataset(path):
    from scripts.ai_eval_fixtures import source_articles, policy_fixture

    dataset = EvalDataset.model_validate_json(path.read_text(encoding="utf-8-sig"))
    if dataset.document_code != "VPP_CP_2021":
        raise ValueError("This fixture supports only VPP_CP_2021")
    articles = source_articles()
    for case in dataset.cases:
        if any(number not in articles for number in case.articles):
            raise ValueError(f"Unknown source article in {case.id}")
    policy_fixture()
    return dataset


class Trace:
    """Observe real service calls without replacing their decisions."""
    def __init__(self, target, method):
        self.target = target
        self.method = method
        self.calls = []

    def __getattr__(self, name):
        if name != self.method:
            return getattr(self.target, name)

        async def observe(**kwargs):
            call = {"input": serializable(kwargs)}
            self.calls.append(call)
            result = await getattr(self.target, name)(**kwargs)
            call["output"] = serializable(result)
            return result
        return observe


def serializable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(item) for item in value]
    return value


class FailureCapture(logging.Handler):
    """Collect only the application's explicitly sanitized failure fields."""
    def __init__(self):
        super().__init__()
        self.events = []

    def emit(self, record):
        if getattr(record, "ai_failure", False):
            self.events.append({key: getattr(record, key, None)
                                for key in ("stage", "error_type", "status_code", "attempt")})


def build_chat(llm, validator, policy, retrieval):
    from app.services.chat_service import ChatService
    from app.services.context_builder import ContextBuilder
    from app.services.critical_flow_service import CriticalFlowService
    from app.services.query_planner import QueryPlanner
    from app.services.safe_response_service import SafeResponseService
    from app.services.safety_classifier import SafetyClassifier
    from app.services.safety_router import SafetyRouter
    from app.services.task_prioritizer import TaskPrioritizer
    from app.services.task_router import TaskRouter
    from scripts.ai_eval_fixtures import MemoryConversations, MemorySink

    planner = Trace(QueryPlanner(llm_service=llm), "plan")
    safety = Trace(SafetyClassifier(llm_service=llm), "classify")
    validation = Trace(validator, "validate")
    service = ChatService(
        retrieval_service=retrieval, llm_service=llm, safety_classifier=safety,
        safety_router=SafetyRouter(), critical_flow_service=CriticalFlowService(),
        query_planner=planner, task_prioritizer=TaskPrioritizer(), task_router=TaskRouter(),
        policy_service=policy, context_builder=ContextBuilder(), response_validator=validation,
        safe_response_service=SafeResponseService(), conversation_service=MemoryConversations(),
        message_source_service=MemorySink(), ai_run_service=MemorySink(),
    )
    return service, {"planner": planner, "safety": safety, "validator": validation}


def chat_behavior(answer, traces):
    from app.services.safe_response_service import SafeResponseService

    if traces["safety"] and traces["safety"][-1].get("output", {}).get("is_critical"):
        return "critical"
    if traces["planner"] and traces["planner"][-1].get("output", {}).get("action") == "NEEDS_CLARIFICATION":
        return "clarify"
    if (answer in {SafeResponseService.HANDOFF_MESSAGE, SafeResponseService.REJECT_MESSAGE,
                   SafeResponseService.POLICY_UNAVAILABLE_MESSAGE}
            or answer == "I do not have enough trusted information to answer this question."):
        return "handoff"
    return "answer"


async def run_case(case, *, llm, validator, retrieval, db, product_version_id):
    from scripts.ai_eval_fixtures import FixturePolicyService, USER_ID, POLICY_ID, task_results

    if case.suite == "validator":
        evidence = task_results(case)
        result = await validator.validate(
            question=case.question, draft_answer=case.draft, task_results=evidence,
            regeneration_count=case.regeneration_count,
        )
        failed = any(issue.code == "VALIDATOR_ERROR" for issue in result.issues)
        return {"validation": result.model_dump(mode="json"),
                "evidence": serializable(evidence), "accepted": result.action == "OK",
                "validator_error": failed}

    service, observers = build_chat(
        llm, validator, FixturePolicyService(case.use_policy, product_version_id), retrieval,
    )
    # Previous assistant turns are generated by the real pipeline, never supplied as gold.
    history = []
    for question in [*case.history, case.question]:
        for observer in observers.values():
            observer.calls.clear()
        answer, conversation_id = await service.generate_answer(
            db=db, message=question, user_id=USER_ID, policy_id=POLICY_ID,
            conversation_id=service.conversation_service.conversation.id if history else None,
        )
        history.append({"question": question, "answer": answer,
                        "trace": {key: list(observer.calls) for key, observer in observers.items()}})
    trace = history[-1]["trace"]
    return {"answer": answer, "turns": history, "observed_behavior": chat_behavior(answer, trace)}


def summarize(rows):
    validator = [row for row in rows if row["suite"] == "validator"]
    chat = [row for row in rows if row["suite"] == "chat"]
    def rate(numerator, denominator):
        return numerator / denominator if denominator else None
    completed = [r for r in validator if r.get("status") == "completed"]
    valid = [r for r in completed if r["expected_accept"]]
    invalid = [r for r in completed if not r["expected_accept"]]
    labeled = [r for r in chat if r.get("status") == "completed"
               and all(isinstance(r.get("review", {}).get(k), bool)
                       for k in ("correct", "grounded", "behavior_correct"))
               and r.get("review", {}).get("reviewer", "").strip()]
    return {
        "cases": len(rows), "execution_errors": sum(r.get("status") == "error" for r in rows),
        "validator": {
            "cases": len(validator), "completed": len(completed),
            "service_failures": sum(r["validator_error"] for r in completed),
            "false_accepts": sum(r["accepted"] for r in invalid),
            "false_accept_rate": rate(sum(r["accepted"] for r in invalid), len(invalid)),
            "blocked_valid": sum(not r["accepted"] for r in valid),
            "blocked_valid_rate": rate(sum(not r["accepted"] for r in valid), len(valid)),
            # Fail-closed service outages are not evidence that a semantic label was understood.
            "label_accuracy_all_cases": rate(sum(
                r["accepted"] == r["expected_accept"] and not r["validator_error"]
                for r in completed), len(validator)),
        },
        "chat": {
            "cases": len(chat), "reviewed": len(labeled),
            "route_matches": sum(r.get("observed_behavior") == r["expected_behavior"] for r in chat),
            "reviewed_correct_rate": rate(sum(r["review"]["correct"] for r in labeled), len(labeled)),
            "reviewed_grounded_rate": rate(sum(r["review"]["grounded"] for r in labeled), len(labeled)),
            "reviewed_behavior_rate": rate(sum(r["review"]["behavior_correct"] for r in labeled), len(labeled)),
        },
    }


async def run(dataset, args):
    from app.core.config import settings
    from app.core.dependencies import get_llm_service, get_response_validator
    from scripts.ai_eval_fixtures import FixtureRetrieval, VERSION_ID, SOURCE, policy_fixture

    # No provider call or model download happens in --check mode.
    llm = get_llm_service()
    validator = get_response_validator()
    db = None
    live_retrieval = None
    product_version_id = VERSION_ID
    cases = [c for c in dataset.cases if args.suite == "all" or c.suite == args.suite]
    if getattr(args, "case", None):
        selected_ids = set(args.case)
        if not selected_ids.issubset({case.id for case in cases}):
            raise ValueError("Unknown case ID or case outside selected suite")
        cases = [case for case in cases if case.id in selected_ids]
    metadata = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": dataset.version, "dataset_sha256": digest(args.dataset.read_bytes()),
        "source_sha256": digest(SOURCE.read_bytes()),
        "policy_fixture_sha256": digest(policy_fixture().model_dump_json().encode()),
        "label_status": dataset.label_status, "retrieval": args.retrieval,
        "provider": settings.llm_provider,
        "model": settings.groq_model if settings.llm_provider == "groq" else settings.gemini_model,
        "scope": "Real AI pipeline; synthetic policy, in-memory conversations; no API/auth or persistence evaluation",
        "planned_case_ids": [case.id for case in cases],
    }
    runtime_source = b"".join(
        str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes()
        for path in sorted((ROOT / "app").rglob("*.py"))
    )
    metadata["runtime_source_sha256"] = digest(runtime_source)
    metadata["harness_sha256"] = digest(
        Path(__file__).read_bytes() + (ROOT / "scripts/ai_eval_fixtures.py").read_bytes()
    )
    repo = str(ROOT.parent).replace("\\", "/")
    metadata["git_commit"] = subprocess.check_output(
        ["git", "-c", f"safe.directory={repo}", "rev-parse", "HEAD"], cwd=ROOT, text=True,
    ).strip()
    rows = []
    try:
        if args.retrieval == "database" and any(c.suite == "chat" for c in cases):
            from app.db.database import SessionLocal
            from scripts.retrieval_scope import resolve_document_scope
            from app.services.retrieval_service import RetrievalService
            db = SessionLocal()
            db.connection().exec_driver_sql("SET TRANSACTION READ ONLY")
            document = resolve_document_scope(db, dataset.document_code, args.product_version_id)
            product_version_id = document.product_version_id
            metadata["document_id"] = str(document.id)
            metadata["product_version_id"] = str(product_version_id)
            live_retrieval = RetrievalService()
        for case in cases:
            row = case.model_dump()
            row["review"] = {"reviewer": "", "correct": None, "grounded": None,
                             "behavior_correct": None, "notes": ""}
            started = time.perf_counter()
            diagnostics = FailureCapture()
            logging.getLogger("app").addHandler(diagnostics)
            try:
                with open(os.devnull, "w") as quiet, redirect_stdout(quiet), redirect_stderr(quiet):
                    result = await asyncio.wait_for(run_case(
                        case, llm=llm, validator=validator, db=db,
                        retrieval=live_retrieval or FixtureRetrieval(case.articles),
                        product_version_id=product_version_id,
                    ), timeout=args.timeout)
                row.update(result, status="completed")
            except Exception as exc:
                row.update(status="error", error_type=type(exc).__name__)
                # Keep credentials and provider payloads out of error reports.
                if db is not None:
                    db.rollback()
                    db.connection().exec_driver_sql("SET TRANSACTION READ ONLY")
            finally:
                logging.getLogger("app").removeHandler(diagnostics)
                row["diagnostics"] = diagnostics.events
            row["latency_seconds"] = round(time.perf_counter() - started, 3)
            rows.append(row)
            complete = len(rows) == len(cases)
            if complete:
                metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
            report = {"metadata": metadata, "complete": complete,
                      "results": rows, "summary": summarize(rows)}
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{case.id}: {row['status']} ({row['latency_seconds']:.1f}s)", flush=True)
    finally:
        if db is not None:
            db.rollback()
            db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--check", action="store_true", help="Validate fixtures only; no models, network or database")
    parser.add_argument("--suite", choices=["all", "chat", "validator"], default="all")
    parser.add_argument("--case", action="append", help="Run a specific case ID; repeat for several cases")
    parser.add_argument("--retrieval", choices=["fixture", "database"], default="fixture")
    parser.add_argument("--product-version-id", type=UUID)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summarize", type=Path, help="Summarize a report after manual review; no inference")
    args = parser.parse_args()
    if args.summarize:
        print(json.dumps(summarize(json.loads(args.summarize.read_text(encoding="utf-8-sig"))["results"]), indent=2))
        return
    dataset = load_dataset(args.dataset)
    if args.check:
        print(f"PASS: {len(dataset.cases)} cases; schema, policy fixture and article references verified.")
        return
    if args.output is None or args.timeout <= 0:
        parser.error("Inference requires --output and a positive --timeout")
    if args.output.exists():
        parser.error("Output already exists; choose a new path to preserve the previous run")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(run(dataset, args))
    print(json.dumps(report["summary"], indent=2))
    if report["summary"]["execution_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
