"""T5.9j — ChatService regeneration/fallback orchestration tests.

These test ChatService's decision handling without calling Gemini or PostgreSQL.
Run from the server directory:
    python -m pytest app/services/test/test_chat_service_regeneration.py -v
"""

import asyncio
from unittest.mock import AsyncMock, Mock

from app.schemas.response_validation import (
    GroundingVerdict,
    ValidationAction,
    ValidationIssue,
    ValidationIssueCode,
    ValidationResult,
)
from app.services.chat_service import ChatService
from app.services.safe_response_service import SafeResponseService


QUESTION = "What is its limit?"
TRUSTED_CONTEXT = "Baggage (BAGGAGE), limit: 100000.00 CZK"
HISTORY = "User: What about baggage?\nAssistant: Your policy includes baggage."
WRONG_DRAFT = "The baggage limit is 500,000 CZK."
CORRECT_DRAFT = "The baggage limit is 100,000 CZK."


def _decision(
    action: ValidationAction,
    grounding: GroundingVerdict,
    issue_code: ValidationIssueCode | None = None,
) -> ValidationResult:
    issues = []
    if issue_code is not None:
        issues.append(
            ValidationIssue(
                code=issue_code,
                message="Draft failed verification.",
                claim=WRONG_DRAFT,
            )
        )
    return ValidationResult(action=action, grounding=grounding, issues=issues)


def _chat_service(*, drafts: list[str], decisions: list[ValidationResult]) -> ChatService:
    """Use real orchestration and fallback logic, mock only its collaborators."""
    service = ChatService(
        retrieval_service=Mock(),
        llm_service=Mock(),
        safety_classifier=Mock(),
        safety_router=Mock(),
        critical_flow_service=Mock(),
        query_planner=Mock(),
        task_prioritizer=Mock(),
        task_router=Mock(),
        policy_service=Mock(),
        context_builder=Mock(),
        response_validator=Mock(),
        safe_response_service=SafeResponseService(),
        conversation_service=Mock(),
        message_source_service=Mock(),
        ai_run_service=Mock(),
    )
    service.llm_service.generate_answer = AsyncMock(side_effect=drafts)
    service.response_validator.validate = AsyncMock(side_effect=decisions)
    return service


def _answer(service: ChatService) -> str:
    return asyncio.run(
        service._generate_validated_answer(
            message=QUESTION,
            context=TRUSTED_CONTEXT,
            task_results=[],  # Validator is mocked; policy fixture tested separately.
            conversation_history=HISTORY,
            system_prompt="You are a careful insurance assistant.",
        )
    )


def test_supported_draft_is_returned_without_regeneration():
    service = _chat_service(
        drafts=[CORRECT_DRAFT],
        decisions=[_decision(ValidationAction.OK, GroundingVerdict.SUPPORTED)],
    )

    assert _answer(service) == CORRECT_DRAFT
    assert service.llm_service.generate_answer.await_count == 1
    assert service.response_validator.validate.await_count == 1
    assert service.response_validator.validate.await_args.kwargs["regeneration_count"] == 0


def test_contradicted_draft_regenerates_once_then_returns_validated_answer():
    service = _chat_service(
        drafts=[WRONG_DRAFT, CORRECT_DRAFT],
        decisions=[
            _decision(
                ValidationAction.REGENERATE,
                GroundingVerdict.CONTRADICTED,
                ValidationIssueCode.CONTRADICTED_CLAIM,
            ),
            _decision(ValidationAction.OK, GroundingVerdict.SUPPORTED),
        ],
    )

    assert _answer(service) == CORRECT_DRAFT
    assert service.llm_service.generate_answer.await_count == 2
    assert service.response_validator.validate.await_count == 2
    assert [
        invocation.kwargs["regeneration_count"]
        for invocation in service.response_validator.validate.await_args_list
    ] == [0, 1]
    second_generation = service.llm_service.generate_answer.await_args_list[1]
    assert WRONG_DRAFT in second_generation.kwargs["context"]
    assert "CONTRADICTED_CLAIM" in second_generation.kwargs["context"]
    assert TRUSTED_CONTEXT in second_generation.kwargs["context"]


def test_regenerated_answer_still_unsupported_returns_safe_fallback():
    service = _chat_service(
        drafts=[WRONG_DRAFT, "Baggage is always covered without exceptions."],
        decisions=[
            _decision(
                ValidationAction.REGENERATE,
                GroundingVerdict.UNSUPPORTED,
                ValidationIssueCode.UNSUPPORTED_CLAIM,
            ),
            _decision(
                ValidationAction.HANDOFF,
                GroundingVerdict.UNSUPPORTED,
                ValidationIssueCode.UNSUPPORTED_CLAIM,
            ),
        ],
    )

    answer = _answer(service)
    assert answer == SafeResponseService.HANDOFF_MESSAGE
    assert answer not in [WRONG_DRAFT, "Baggage is always covered without exceptions."]
    assert service.llm_service.generate_answer.await_count == 2
    assert service.response_validator.validate.await_count == 2


def test_model_b_service_failure_returns_handoff_without_regeneration():
    service = _chat_service(
        drafts=[CORRECT_DRAFT],
        decisions=[
            _decision(
                ValidationAction.HANDOFF,
                GroundingVerdict.NOT_CHECKED,
                ValidationIssueCode.VALIDATOR_ERROR,
            )
        ],
    )

    assert _answer(service) == SafeResponseService.HANDOFF_MESSAGE
    assert service.llm_service.generate_answer.await_count == 1
    assert service.response_validator.validate.await_count == 1


def test_rejected_draft_is_never_returned():
    service = _chat_service(
        drafts=[WRONG_DRAFT],
        decisions=[
            _decision(
                ValidationAction.REJECT,
                GroundingVerdict.NOT_CHECKED,
                ValidationIssueCode.INVALID_RUNTIME_STATE,
            )
        ],
    )

    assert _answer(service) == SafeResponseService.REJECT_MESSAGE
    assert service.llm_service.generate_answer.await_count == 1
    assert service.response_validator.validate.await_count == 1
