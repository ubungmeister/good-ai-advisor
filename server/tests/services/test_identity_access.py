"""Access boundaries without a database, model downloads or LLM calls."""

import asyncio
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import chat, llm, policies, users
from app.core import identity
from app.core.config import settings
from app.core.dependencies import get_chat_service, get_llm_service
from app.db.dependencies import get_db
from app.services.access_errors import ResourceNotFoundError
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.models import ConversationRole
from app.schemas.safety import SafetyRoute


@pytest.fixture
def api(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4(), status="ACTIVE")
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "dev_user_id", str(user.id))
    monkeypatch.setattr(settings, "dev_policy_id", str(uuid.uuid4()))
    lookup = Mock(return_value=user)
    monkeypatch.setattr(identity, "get_user_by_id", lookup)
    app = FastAPI()
    for router in [chat.router, policies.router, users.router, llm.router]:
        app.include_router(router)
    db = Mock()
    service = Mock()
    service.generate_answer = AsyncMock(return_value=("Supported answer", uuid.uuid4()))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_chat_service] = lambda: service
    app.dependency_overrides[get_llm_service] = lambda: Mock()
    return SimpleNamespace(client=TestClient(app), user=user, service=service, db=db, lookup=lookup)


@pytest.mark.parametrize("path", ["/chat", "/api/users/me", "/api/policies", "/api/llm/test"])
@pytest.mark.parametrize("environment", ["production", "staging", ""])
def test_non_development_requests_fail_closed(api, monkeypatch, path, environment):
    monkeypatch.setattr(settings, "environment", environment)
    response = (api.client.post(path, json={"message": "hello"}) if path == "/chat"
                else api.client.get(path))
    assert response.status_code == 401
    api.lookup.assert_not_called()
    api.service.generate_answer.assert_not_awaited()


@pytest.mark.parametrize("configured_id", ["", "invalid"])
def test_invalid_demo_identity_is_a_configuration_error(api, monkeypatch, configured_id):
    monkeypatch.setattr(settings, "dev_user_id", configured_id)
    assert api.client.post("/chat", json={"message": "hello"}).status_code == 503
    api.lookup.assert_not_called()


@pytest.mark.parametrize("user", [None, SimpleNamespace(status="DISABLED")])
def test_missing_or_inactive_demo_user_is_rejected(api, user):
    api.lookup.return_value = user
    assert api.client.post("/chat", json={"message": "hello"}).status_code == 401
    api.service.generate_answer.assert_not_awaited()


def test_chat_rejects_body_identity_and_query_identity(api):
    assert api.client.post("/chat", json={
        "message": "hello", "user_id": str(uuid.uuid4()),
    }).status_code == 422
    assert api.client.post("/chat?user_id=" + str(uuid.uuid4()), json={
        "message": "hello",
    }).status_code == 400
    api.service.generate_answer.assert_not_awaited()


def test_chat_uses_server_identity_and_default_policy(api):
    assert api.client.post("/chat", json={"message": "hello"}).status_code == 200
    kwargs = api.service.generate_answer.await_args.kwargs
    assert kwargs["user_id"] == api.user.id
    assert kwargs["policy_id"] == uuid.UUID(settings.dev_policy_id)


def test_continuation_does_not_inherit_default_policy(api):
    response = api.client.post("/chat", json={
        "message": "hello", "conversation_id": str(uuid.uuid4()),
    })
    assert response.status_code == 200
    assert api.service.generate_answer.await_args.kwargs["policy_id"] is None


def test_policy_list_uses_server_identity(api, monkeypatch):
    service = Mock()
    service.get_policies_for_user.return_value = []
    monkeypatch.setattr(policies, "policy_service", service)
    assert api.client.get("/api/policies").json() == []
    service.get_policies_for_user.assert_called_once_with(db=api.db, user_id=api.user.id)


@pytest.mark.parametrize("suffix", ["", "/details"])
def test_foreign_policy_is_hidden_and_query_identity_rejected(api, monkeypatch, suffix):
    service = Mock()
    service.get_policy_for_user.return_value = None
    service.get_policy_details_for_user.return_value = None
    monkeypatch.setattr(policies, "policy_service", service)
    path = "/api/policies/" + str(uuid.uuid4()) + suffix
    assert api.client.get(path).status_code == 404
    method = (service.get_policy_details_for_user if suffix else service.get_policy_for_user)
    assert method.call_args.kwargs["user_id"] == api.user.id
    assert api.client.get(path + "?user_id=" + str(uuid.uuid4())).status_code == 400
    assert method.call_count == 1


def test_chat_errors_do_not_log_sensitive_exception(api, caplog, capsys):
    secret = "PRIVATE_MESSAGE_AND_POLICY_123"
    api.service.generate_answer.side_effect = RuntimeError(secret)
    with caplog.at_level(logging.INFO):
        response = api.client.post("/chat", json={"message": secret})
    assert response.status_code == 503
    assert "Chat request failed" in caplog.text
    assert secret not in caplog.text + capsys.readouterr().out + response.text


def test_access_error_remains_404(api):
    api.service.generate_answer.side_effect = ResourceNotFoundError("private resource")
    response = api.client.post("/chat", json={"message": "hello"})
    assert response.status_code == 404
    assert "private resource" not in response.text


@pytest.mark.parametrize("scenario", ["foreign_conversation", "foreign_policy", "revoked_policy", "switch_policy"])
def test_chat_access_denied_before_history_message_or_model_work(scenario):
    service = ChatService.__new__(ChatService)
    conversations = ConversationService()
    conversations.conversation_repository = Mock()
    conversations.message_repository = Mock()
    conversations.policy_service = Mock()
    conversations.policy_service.get_policy_for_user.return_value = None
    service.conversation_service = conversations
    service.safety_classifier = Mock()
    user_id, policy_id, conversation_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conversations.conversation_repository.get_by_id_for_user.return_value = (
        None if scenario == "foreign_conversation" else
        SimpleNamespace(id=conversation_id, policy_id=policy_id)
    )
    db = Mock()
    with pytest.raises(ResourceNotFoundError):
        asyncio.run(service.generate_answer(
            db=db, message="private", user_id=user_id,
            conversation_id=None if scenario == "foreign_policy" else conversation_id,
            policy_id=uuid.uuid4() if scenario == "switch_policy" else policy_id,
        ))
    conversations.conversation_repository.create.assert_not_called()
    conversations.message_repository.assert_not_called()
    assert conversations.message_repository.mock_calls == []
    service.safety_classifier.assert_not_called()
    assert service.safety_classifier.mock_calls == []
    db.commit.assert_not_called()


@pytest.mark.parametrize("continuing", [False, True])
def test_owned_policy_can_start_or_continue_a_conversation(continuing):
    service = ConversationService()
    service.policy_service = Mock()
    service.conversation_repository = Mock()
    user_id, policy_id = uuid.uuid4(), uuid.uuid4()
    conversation = SimpleNamespace(id=uuid.uuid4(), policy_id=policy_id)
    service.conversation_repository.create.return_value = conversation
    service.conversation_repository.get_by_id_for_user.return_value = conversation
    service.policy_service.get_policy_for_user.return_value = object()
    assert service.get_or_create(
        db=Mock(), user_id=user_id, policy_id=policy_id,
        conversation_id=conversation.id if continuing else None,
    ) is conversation
    assert service.policy_service.get_policy_for_user.call_args.kwargs["user_id"] == user_id


def test_chat_history_identity_and_safety_results_are_not_logged(caplog, capsys):
    service = ChatService.__new__(ChatService)
    service.conversation_service = Mock()
    conversation_id, user_id, policy_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service.conversation_service.get_or_create.return_value = SimpleNamespace(
        id=conversation_id, policy_id=policy_id,
    )
    service.conversation_service.get_recent_messages.return_value = [
        SimpleNamespace(role=ConversationRole.USER, content="PRIVATE_HISTORY"),
    ]
    service.safety_classifier = Mock()
    service.safety_classifier.classify = AsyncMock(return_value=SimpleNamespace(
        category=SimpleNamespace(value="PRIVATE_SAFETY"),
    ))
    service.safety_router = Mock()
    service.safety_router.route.return_value = SafetyRoute.CRITICAL_FLOW
    service.critical_flow_service = Mock()
    service.critical_flow_service.handle.return_value = "PRIVATE_ANSWER"
    service._save_assistant_answer = Mock(return_value="PRIVATE_ANSWER")
    with caplog.at_level(logging.DEBUG):
        answer, _ = asyncio.run(service.generate_answer(
            db=Mock(), message="PRIVATE_MESSAGE", user_id=user_id,
        ))
    assert answer == "PRIVATE_ANSWER"
    captured = capsys.readouterr()
    output = caplog.text + captured.out + captured.err
    for private_value in ["PRIVATE_HISTORY", "PRIVATE_SAFETY", "PRIVATE_ANSWER", "PRIVATE_MESSAGE",
                          str(conversation_id), str(user_id), str(policy_id)]:
        assert private_value not in output
