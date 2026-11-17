import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from app.llm.providers import gemini_provider
from app.schemas.query_plan import QueryPlan, PlannedTask
from app.schemas.safety import SafetyDecision
from app.services.chat_service import ChatService
from app.services.safe_response_service import SafeResponseService
from app.services.task_prioritizer import TaskPrioritizer
from app.services.task_router import TaskRouter
from app.services.query_planner import QueryPlanner
from scripts.ai_eval_fixtures import MemoryConversations, MemorySink


@pytest.mark.parametrize("task_type,missing_id", [("POLICY_DETAILS", False),
    ("POLICY_DETAILS", True), ("GENERAL_QUESTION", False), ("GENERAL_QUESTION", True),
    ("COVERAGE_CHECK", False)])
def test_unavailable_policy_is_saved_as_handoff_without_generator_or_retrieval(task_type, missing_id):
    service = ChatService.__new__(ChatService)
    service.conversation_service = MemoryConversations()
    if missing_id:
        service.conversation_service.conversation.policy_id = None
    service.ai_run_service = MemorySink()
    service.message_source_service = MemorySink()
    service.safety_classifier = Mock(classify=AsyncMock(return_value=SafetyDecision(
        is_critical=False, category="NONE")))
    service.safety_router = Mock()
    service.query_planner = Mock(plan=AsyncMock(return_value=QueryPlan(action="EXECUTE", tasks=[
        PlannedTask(type=task_type, query="policy question", evidence="policy question")
    ])))
    service.task_prioritizer = TaskPrioritizer()
    service.task_router = TaskRouter()
    service.policy_service = Mock()
    service.policy_service.get_policy_for_user.return_value = None
    service.policy_service.get_policy_details_for_user.return_value = None
    service.retrieval_service = Mock()
    service.llm_service = Mock(generate_answer=AsyncMock())
    service.response_validator = Mock(validate=AsyncMock())
    answer, conversation_id = asyncio.run(service.generate_answer(
        db=None, message="policy question", user_id=uuid4(),
    ))
    assert answer == SafeResponseService.POLICY_UNAVAILABLE_MESSAGE
    assert conversation_id == service.conversation_service.conversation.id
    assert [message.content for message in service.conversation_service.messages] == ["policy question", answer]
    service.llm_service.generate_answer.assert_not_awaited()
    service.response_validator.validate.assert_not_awaited()
    service.retrieval_service.search.assert_not_called()


def test_planner_translates_query_but_keeps_original_evidence_contract(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "retrieval_query_language", "Czech")
    message = "What must I do after baggage robbery?"
    llm = Mock(generate_structured=AsyncMock(return_value=QueryPlan(action="EXECUTE", tasks=[
        PlannedTask(type="PROCEDURE", query="Jak postupovat při loupeži zavazadel?", evidence=message)
    ])))
    result = asyncio.run(QueryPlanner(llm_service=llm).plan(message=message))
    assert result.tasks[0].evidence == message
    prompt = llm.generate_structured.await_args.kwargs["system_prompt"]
    assert "task.query in Czech" in prompt
    assert "evidence verbatim" in prompt
    assert llm.generate_structured.await_args.kwargs["user_message"] == message


class ProviderError(Exception):
    def __init__(self, code):
        super().__init__("PRIVATE_PROVIDER_PAYLOAD")
        self.status_code = code


@pytest.fixture
def provider(monkeypatch):
    client = Mock()
    client.aio.interactions.create = AsyncMock()
    monkeypatch.setattr(gemini_provider.genai, "Client", Mock(return_value=client))
    instance = gemini_provider.GeminiProvider(api_key="test", model="test")
    return instance


def test_transient_failure_retries_once_without_logging_payload(provider, monkeypatch, caplog):
    sleep = AsyncMock()
    monkeypatch.setattr(gemini_provider.asyncio, "sleep", sleep)
    provider._async_client.interactions.create.side_effect = [ProviderError(503), SimpleNamespace(output_text="answer")]
    with caplog.at_level(logging.WARNING):
        assert asyncio.run(provider.generate(system_prompt="test", user_message="PRIVATE_QUESTION")) == "answer"
    assert provider._async_client.interactions.create.await_count == 2
    assert sleep.await_count == 1
    assert "PRIVATE_PROVIDER_PAYLOAD" not in caplog.text
    assert "PRIVATE_QUESTION" not in caplog.text
    assert "status=503" in caplog.text


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_permanent_failure_is_not_retried(provider, code):
    provider._async_client.interactions.create.side_effect = ProviderError(code)
    with pytest.raises(ProviderError):
        asyncio.run(provider.generate(system_prompt="test", user_message="test"))
    assert provider._async_client.interactions.create.await_count == 1


def test_cancellation_is_not_retried(provider):
    provider._async_client.interactions.create.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(provider.generate(system_prompt="test", user_message="test"))
    assert provider._async_client.interactions.create.await_count == 1


def test_expired_call_deadline_cancels_request(provider):
    async def hanging(**kwargs):
        await asyncio.sleep(10)
    provider.call_timeout = 0.02
    provider.request_timeout = 1
    provider._async_client.interactions.create.side_effect = hanging
    with pytest.raises(TimeoutError):
        asyncio.run(provider.generate(system_prompt="test", user_message="test"))
    assert provider._async_client.interactions.create.await_count == 1


def test_bad_structured_output_is_not_retried_as_a_transport_failure(provider):
    class Schema(BaseModel):
        answer: str
    provider._async_client.interactions.create.return_value = SimpleNamespace(output_text="not JSON")
    with pytest.raises(ValidationError):
        asyncio.run(provider.generate_structured(system_prompt="test", user_message="test", response_model=Schema))
    assert provider._async_client.interactions.create.await_count == 1
