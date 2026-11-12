"""Regression tests for T5.9: independent of Gemini and PostgreSQL."""

import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from app.models.policy import PaymentStatus, PolicyStatus
from app.schemas.policy import (
    CoverageTypeResponse,
    PolicyCoverageResponse,
    PolicyResponse,
)
from app.schemas.query_plan import TaskType
from app.schemas.response_validation import (
    GroundingCheckResult,
    GroundingClaim,
    GroundingVerdict,
    ValidationAction,
    ValidationIssueCode,
)
from app.schemas.task_result import PolicyTaskContent, TaskResult
from app.schemas.task_routing import TaskTarget
from app.services.deterministic_guard_service import DeterministicGuardService
from app.services.grounding_fact_builder import GroundingFactBuilder
from app.services.grounding_validator import GroundingValidator
from app.services.response_validator import ResponseValidator
from app.services.validation_decision_policy import ValidationDecisionPolicy

POLICY_ID = UUID("5c00c41d-f376-4738-8555-9b28599264f6")
BAGGAGE_ID = UUID("8877ad6f-0aca-4cc0-b590-5a94de16aa30")
BAGGAGE_EVIDENCE_ID = f"policy.coverage:{BAGGAGE_ID}"
QUESTION = "What is its limit?"
CORRECT_ANSWER = "The baggage limit is 100,000 CZK."
WRONG_ANSWER = "The baggage limit is 500,000 CZK."


def _policy_task_results() -> list[TaskResult]:
    """Small policy fixture using the real Pydantic TaskResult schemas."""
    return [
        TaskResult(
            task_type=TaskType.POLICY_DETAILS,
            target=TaskTarget.POLICY,
            content=PolicyTaskContent(
                policy=PolicyResponse(
                    id=POLICY_ID,
                    policy_number="TI-2026-0001",
                    policy_status=PolicyStatus.ACTIVE,
                    payment_status=PaymentStatus.PAID,
                    start_date=date(2026, 9, 1),
                    end_date=date(2026, 9, 15),
                    premium_amount=Decimal("1290.00"),
                    currency="CZK",
                    paid_at=None,
                ),
                coverages=[
                    PolicyCoverageResponse(
                        id=BAGGAGE_ID,
                        limit_amount=Decimal("100000.00"),
                        currency="CZK",
                        coverage_type=CoverageTypeResponse(
                            code="BAGGAGE", name="Baggage"
                        ),
                    )
                ],
                options=[],
                people=[],
                travel_details=None,
            ),
        )
    ]


def _grounding_result(
        verdict: GroundingVerdict,
        *,
        claim: str,
        supported: bool,
        evidence_ids: list[str] | None = None,
) -> GroundingCheckResult:
    return GroundingCheckResult(
        verdict=verdict,
        support_score=None,
        claims=[
            GroundingClaim(
                claim=claim,
                grounding_required=True,
                supported=supported,
                evidence_ids=(
                    evidence_ids
                    if evidence_ids is not None
                    else ([BAGGAGE_EVIDENCE_ID] if supported else [])
                ),
                score=None,
            )
        ],
    )


def _validator_with_judge(judge: object) -> ResponseValidator:
    return ResponseValidator(
        guard_service=DeterministicGuardService(),
        grounding_fact_builder=GroundingFactBuilder(),
        grounding_validator=judge,
        decision_policy=ValidationDecisionPolicy(),
    )


def _run(
        validator: ResponseValidator,
        *,
        answer: str = CORRECT_ANSWER,
        task_results: list[TaskResult] | None = None,
        regeneration_count: int = 0,
):
    return asyncio.run(
        validator.validate(
            question=QUESTION,
            draft_answer=answer,
            task_results=(
                _policy_task_results() if task_results is None else task_results
            ),
            regeneration_count=regeneration_count,
        )
    )


def test_supported_baggage_limit_is_released_only_after_model_b_passes():
    judge = Mock()
    judge.validate = AsyncMock(
        return_value=_grounding_result(
            GroundingVerdict.SUPPORTED,
            claim=CORRECT_ANSWER,
            supported=True,
        )
    )

    result = _run(_validator_with_judge(judge))

    assert result.action == ValidationAction.OK
    assert result.grounding == GroundingVerdict.SUPPORTED
    assert result.issues == []
    judge.validate.assert_awaited_once()
    facts = judge.validate.await_args.kwargs["facts"]
    baggage_fact = next(f for f in facts if f.id == BAGGAGE_EVIDENCE_ID)
    assert "100000.00 CZK" in baggage_fact.text


@pytest.mark.parametrize(
    "regeneration_count, expected_action",
    [(0, ValidationAction.REGENERATE), (1, ValidationAction.HANDOFF)],
)
def test_contradicted_limit_is_never_released(
        regeneration_count, expected_action
):
    judge = Mock()
    judge.validate = AsyncMock(
        return_value=_grounding_result(
            GroundingVerdict.CONTRADICTED,
            claim=WRONG_ANSWER,
            supported=False,
            evidence_ids=[BAGGAGE_EVIDENCE_ID],
        )
    )

    result = _run(
        _validator_with_judge(judge),
        answer=WRONG_ANSWER,
        regeneration_count=regeneration_count,
    )

    assert result.action == expected_action
    assert result.grounding == GroundingVerdict.CONTRADICTED
    assert result.issues[0].code == ValidationIssueCode.CONTRADICTED_CLAIM
    assert result.issues[0].claim == WRONG_ANSWER


def test_unsupported_claim_triggers_regeneration():
    judge = Mock()
    judge.validate = AsyncMock(
        return_value=_grounding_result(
            GroundingVerdict.UNSUPPORTED,
            claim="Heli-skiing is always covered.",
            supported=False,
            evidence_ids=[],
        )
    )

    result = _run(_validator_with_judge(judge), answer="Heli-skiing is always covered.")

    assert result.action == ValidationAction.REGENERATE
    assert result.issues[0].code == ValidationIssueCode.UNSUPPORTED_CLAIM


def test_model_b_503_fails_closed_without_releasing_draft():
    judge = Mock()
    judge.validate = AsyncMock(side_effect=RuntimeError("503 service_unavailable"))

    result = _run(_validator_with_judge(judge))

    assert result.action == ValidationAction.HANDOFF
    assert result.grounding == GroundingVerdict.NOT_CHECKED
    assert any(issue.code == ValidationIssueCode.VALIDATOR_ERROR for issue in result.issues)


def test_missing_trusted_evidence_never_calls_model_b():
    judge = Mock()
    judge.validate = AsyncMock()

    result = _run(_validator_with_judge(judge), task_results=[])

    assert result.action == ValidationAction.HANDOFF
    assert any(
        issue.code == ValidationIssueCode.NO_TRUSTED_EVIDENCE
        for issue in result.issues
    )
    judge.validate.assert_not_awaited()


def test_empty_draft_regenerates_without_model_b():
    judge = Mock()
    judge.validate = AsyncMock()

    result = _run(_validator_with_judge(judge), answer="   ")

    assert result.action == ValidationAction.REGENERATE
    assert any(issue.code == ValidationIssueCode.EMPTY_ANSWER for issue in result.issues)
    judge.validate.assert_not_awaited()


def test_model_b_invented_evidence_id_is_rejected():
    """Use the real GroundingValidator, not a mocked judge, for ID checking."""
    fake_llm = Mock()
    fake_llm.generate_structured = AsyncMock(
        return_value=_grounding_result(
            GroundingVerdict.SUPPORTED,
            claim=CORRECT_ANSWER,
            supported=True,
            evidence_ids=["made-up-evidence-id"],
        )
    )
    judge = GroundingValidator(llm_service=fake_llm)

    result = _run(_validator_with_judge(judge))

    assert result.action == ValidationAction.HANDOFF
    assert result.grounding == GroundingVerdict.NOT_CHECKED
    assert any(issue.code == ValidationIssueCode.VALIDATOR_ERROR for issue in result.issues)
    fake_llm.generate_structured.assert_awaited_once()
