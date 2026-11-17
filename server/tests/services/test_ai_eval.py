"""Benchmark harness tests. Scripted models here are never AI quality measurements."""

import asyncio
from argparse import Namespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.schemas.ai_eval import EvalCase, EvalDataset
from app.schemas.query_plan import QueryPlan, QueryPlanAction, PlannedTask, TaskType
from app.schemas.response_validation import ValidationAction, ValidationResult, GroundingVerdict
from app.schemas.safety import SafetyDecision, SafetyCategory
from scripts.ai_eval_fixtures import FixtureRetrieval, VERSION_ID, task_results
from scripts.run_ai_eval import DEFAULT_DATASET, load_dataset, run_case, summarize


def case(**overrides):
    return EvalCase.model_validate({"id": "example", "suite": "chat", "category": "policy",
                                    "question": "What is the baggage limit?",
                                    "rubric": ["100000 CZK, no promise of payout"], **overrides})


def test_dataset_has_both_suites_and_source_backed_reference_evidence():
    dataset = load_dataset(DEFAULT_DATASET)
    assert {c.suite for c in dataset.cases} == {"chat", "validator"}
    assert {c.expected_accept for c in dataset.cases if c.suite == "validator"} == {True, False}
    for c in dataset.cases:
        for result in task_results(c):
            if result.target == "RETRIEVAL":
                assert result.content.chunks[0].content
                assert result.content.chunks[0].page_number


def test_new_paraphrases_have_valid_source_references_and_distinct_questions():
    reference = load_dataset(DEFAULT_DATASET)
    extra = load_dataset(DEFAULT_DATASET.with_name("ai_eval_paraphrases.json"))
    assert len(extra.cases) == 3
    assert not {c.question for c in reference.cases} & {c.question for c in extra.cases}
    assert all(c.articles and c.rubric for c in extra.cases)


def test_dataset_rejects_duplicate_ids_and_incomplete_labels():
    with pytest.raises(ValidationError):
        EvalDataset(version="1", document_code="test", label_status="draft", cases=[case(), case()])
    with pytest.raises(ValidationError):
        case(suite="validator", draft="an answer")


def test_dataset_rejects_invalid_article_reference(tmp_path):
    payload = load_dataset(DEFAULT_DATASET).model_dump()
    payload["cases"][0]["articles"] = [9999]
    import json
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown source article"):
        load_dataset(path)


def test_metric_denominators_include_execution_errors_and_do_not_credit_service_failure():
    rows = [
        {"suite": "validator", "status": "completed", "expected_accept": False,
         "accepted": True, "validator_error": False},
        {"suite": "validator", "status": "completed", "expected_accept": False,
         "accepted": False, "validator_error": True},
        {"suite": "validator", "status": "completed", "expected_accept": True,
         "accepted": True, "validator_error": False},
        {"suite": "validator", "status": "error", "expected_accept": True},
    ]
    metrics = summarize(rows)["validator"]
    assert metrics["false_accepts"] == 1
    assert metrics["service_failures"] == 1
    assert metrics["label_accuracy_all_cases"] == 0.25


def test_unreviewed_answers_are_not_counted_as_correct():
    row = {"suite": "chat", "status": "completed", "expected_behavior": "answer",
           "observed_behavior": "answer", "review": {}}
    assert summarize([row])["chat"]["reviewed_correct_rate"] is None
    row["review"] = {"correct": True, "grounded": False, "behavior_correct": True, "reviewer": ""}
    assert summarize([row])["chat"]["reviewed"] == 0
    row["review"]["reviewer"] = "Reviewer"
    assert summarize([row])["chat"]["reviewed_correct_rate"] == 1
    assert summarize([row])["chat"]["reviewed_grounded_rate"] == 0


class ScriptedLLM:
    def __init__(self, clarify=False):
        self.clarify = clarify
        self.generate_answer = AsyncMock(return_value="The baggage limit is 100,000 CZK.")

    async def generate_structured(self, **kwargs):
        if kwargs["response_model"] is SafetyDecision:
            return SafetyDecision(is_critical=False, category=SafetyCategory.NONE)
        assert kwargs["response_model"] is QueryPlan
        if self.clarify:
            return QueryPlan(action=QueryPlanAction.NEEDS_CLARIFICATION,
                             clarification_question="Which coverage do you mean?")
        return QueryPlan(action=QueryPlanAction.EXECUTE, tasks=[PlannedTask(
            type=TaskType.POLICY_DETAILS, query=kwargs["user_message"], evidence=kwargs["user_message"],
        )])


def test_chat_harness_runs_real_routing_context_and_multi_turn_flow():
    llm = ScriptedLLM()
    validator = type("Validator", (), {})()
    validator.validate = AsyncMock(return_value=ValidationResult(
        action=ValidationAction.OK, grounding=GroundingVerdict.SUPPORTED,
    ))
    result = asyncio.run(run_case(
        case(history=["What is the baggage limit?"]), llm=llm, validator=validator,
        retrieval=FixtureRetrieval([]), db=None, product_version_id=VERSION_ID,
    ))
    assert result["observed_behavior"] == "answer"
    assert len(result["turns"]) == 2
    assert "100000.00" in llm.generate_answer.await_args.kwargs["context"]
    assert "CONVERSATION HISTORY" in llm.generate_answer.await_args.kwargs["context"]
    assert result["turns"][-1]["trace"]["validator"][0]["input"]["task_results"]


def test_clarification_does_not_call_generator_or_validator():
    llm = ScriptedLLM(clarify=True)
    validator = type("Validator", (), {})()
    validator.validate = AsyncMock()
    result = asyncio.run(run_case(case(), llm=llm, validator=validator,
                                 retrieval=FixtureRetrieval([]), db=None, product_version_id=VERSION_ID))
    assert result["observed_behavior"] == "clarify"
    llm.generate_answer.assert_not_awaited()
    validator.validate.assert_not_awaited()


def test_validator_harness_preserves_label_and_captures_actual_decision():
    c = case(suite="validator", draft="The limit is 500000 CZK", expected_accept=False)
    validator = type("Validator", (), {})()
    validator.validate = AsyncMock(return_value=ValidationResult(action="OK", grounding="SUPPORTED"))
    result = asyncio.run(run_case(c, llm=None, validator=validator, retrieval=None,
                                 db=None, product_version_id=VERSION_ID))
    assert result["accepted"] is True  # An actual false accept, not the expected result.
    assert c.expected_accept is False
    assert result["evidence"][0]["content"]["coverages"][0]["limit_amount"] == "100000.00"


def test_case_errors_are_checkpointed_without_exception_payload(tmp_path, monkeypatch):
    import json
    from app.core import dependencies
    from scripts import run_ai_eval

    monkeypatch.setattr(dependencies, "get_llm_service", lambda: object())
    monkeypatch.setattr(dependencies, "get_response_validator", lambda: object())
    monkeypatch.setattr(run_ai_eval, "run_case", AsyncMock(side_effect=RuntimeError("SECRET_PROVIDER_PAYLOAD")))
    args = Namespace(suite="chat", dataset=DEFAULT_DATASET, retrieval="fixture", timeout=1,
                     output=tmp_path / "report.json")
    report = asyncio.run(run_ai_eval.run(load_dataset(DEFAULT_DATASET), args))
    saved = json.loads(args.output.read_text(encoding="utf-8"))
    assert saved["summary"]["execution_errors"] == 10
    assert report["summary"] == saved["summary"]
    assert saved["complete"] is True
    assert len(saved["metadata"]["runtime_source_sha256"]) == 64
    assert "SECRET_PROVIDER_PAYLOAD" not in args.output.read_text(encoding="utf-8")
    assert saved["summary"]["chat"]["reviewed_correct_rate"] is None


def test_summarize_accepts_a_report_saved_with_windows_utf8_bom(tmp_path, monkeypatch, capsys):
    import json
    import sys
    from scripts.run_ai_eval import main

    report = tmp_path / "reviewed.json"
    report.write_text(json.dumps({"results": []}), encoding="utf-8-sig")
    monkeypatch.setattr(sys, "argv", ["run_ai_eval", "--summarize", str(report)])
    main()
    assert json.loads(capsys.readouterr().out)["cases"] == 0
