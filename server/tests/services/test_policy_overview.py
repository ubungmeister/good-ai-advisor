import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.schemas.query_plan import PlannedTask, QueryPlan
from app.schemas.safety import SafetyDecision, SafetyRoute
from app.services.chat_service import ChatService
from app.services.policy_overview import render_policy_overview
from scripts.ai_eval_fixtures import FixturePolicyService, FixtureRetrieval, USER_ID, POLICY_ID
from scripts.benchmark_policy_overview import overview_fixture
from scripts.run_ai_eval import build_chat


def test_overview_formats_only_recorded_coverages_and_selected_options():
    data = overview_fixture()
    before = data.model_dump_json()
    answer = render_policy_overview(data, "en")
    for value in ["Medical Expenses", "100,000,000.00 CZK", "Liability", "20,000,000.00 CZK",
                  "Baggage", "100,000.00 CZK", "Assistance Services", "Winter Sports", "Trip Cancellation"]:
        assert value in answer
    for omitted in ["Vehicle Assistance", "1290", "2026-09-01", "ACTIVE", "Eval Person"]:
        assert omitted not in answer
    assert "not a decision on a particular claim" in answer
    assert data.model_dump_json() == before


def test_formatter_does_not_invent_missing_currency_or_coverages():
    data = overview_fixture()
    data.coverages = [data.coverages[0]]
    data.coverages[0].currency = None
    data.options = []
    assert "CZK" not in render_policy_overview(data, "en")
    data.coverages = []
    assert "No coverages are listed in the available records" in render_policy_overview(data, "en")
    with pytest.raises(ValueError):
        render_policy_overview(data, "de")


def test_overview_flag_cannot_be_used_for_a_coverage_decision():
    with pytest.raises(ValidationError):
        PlannedTask(type="COVERAGE_CHECK", query="covered?", evidence="covered?", policy_overview_language="en")


def test_overview_uses_owned_policy_data_without_generator_or_semantic_judge():
    class Policy(FixturePolicyService):
        def get_policy_details_for_user(self, **kwargs):
            assert kwargs["user_id"] == USER_ID and kwargs["policy_id"] == POLICY_ID
            return overview_fixture()

    llm = Mock(generate_structured=AsyncMock(), generate_answer=AsyncMock())
    validator = Mock(validate=AsyncMock())
    service, _ = build_chat(llm, validator, Policy(), FixtureRetrieval([]))
    service.safety_classifier.classify = AsyncMock(return_value=SafetyDecision(is_critical=False, category="NONE"))
    service.query_planner.plan = AsyncMock(return_value=QueryPlan(action="EXECUTE", tasks=[PlannedTask(
        type="POLICY_DETAILS", query="overview", evidence="overview", policy_overview_language="en")]))
    service.ai_run_service = Mock()
    answer, _ = asyncio.run(service.generate_answer(db=None, message="overview", user_id=USER_ID))
    assert answer == render_policy_overview(overview_fixture(), "en")
    llm.generate_answer.assert_not_awaited()
    validator.validate.assert_not_awaited()
    assert service.ai_run_service.save_run.call_args.kwargs["answer_source"] == "policy-overview-v1"
    assert service.conversation_service.messages[-1].content == answer


def test_safety_and_planning_overlap_without_executing_a_task():
    async def run():
        safety_started, planning_started = asyncio.Event(), asyncio.Event()
        async def safety(**kwargs):
            safety_started.set()
            await planning_started.wait()
            return SafetyDecision(is_critical=False, category="NONE")
        async def plan(**kwargs):
            planning_started.set()
            await safety_started.wait()
            return "planned"
        service = ChatService.__new__(ChatService)
        service.safety_classifier = Mock(classify=safety)
        service.query_planner = Mock(plan=plan)
        service.safety_router = Mock(route=Mock(return_value=SafetyRoute.NORMAL_FLOW))
        _, route, task = await asyncio.wait_for(service._prepare_turn(message="test", conversation_history=""), 1)
        assert route == SafetyRoute.NORMAL_FLOW
        assert await task == "planned"
    asyncio.run(run())


@pytest.mark.parametrize("failed_safety", [False, True])
def test_critical_or_failed_safety_cancels_read_only_planning(failed_safety):
    async def run():
        started, cancelled = asyncio.Event(), asyncio.Event()
        async def plan(**kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        async def safety(**kwargs):
            await started.wait()
            if failed_safety:
                raise TimeoutError()
            return SafetyDecision(is_critical=True, category="OTHER_CRITICAL", evidence=["test"])
        service = ChatService.__new__(ChatService)
        service.query_planner = Mock(plan=plan)
        service.safety_classifier = Mock(classify=safety)
        service.safety_router = Mock(route=Mock(return_value=SafetyRoute.CRITICAL_FLOW))
        if failed_safety:
            with pytest.raises(TimeoutError):
                await service._prepare_turn(message="test", conversation_history="")
        else:
            _, route, task = await service._prepare_turn(message="test", conversation_history="")
            assert route == SafetyRoute.CRITICAL_FLOW and task is None
        assert cancelled.is_set()
    asyncio.run(run())
