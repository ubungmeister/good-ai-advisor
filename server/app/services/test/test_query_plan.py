
import pytest
from pydantic import ValidationError

from app.schemas.query_plan import (
    PlannedTask,
    QueryPlan,
    QueryPlanAction,
    TaskType,
)


def test_execute_plan_requires_tasks():
    with pytest.raises(ValidationError):
        QueryPlan(
            action=QueryPlanAction.EXECUTE,
            tasks=[],
        )


def test_execute_plan_accepts_tasks():
    plan = QueryPlan(
        action=QueryPlanAction.EXECUTE,
        tasks=[
            PlannedTask(
                type=TaskType.POLICY_DETAILS,
                query="When does my policy expire?",
                evidence="my policy expire",
            )
        ],
    )

    assert plan.action == QueryPlanAction.EXECUTE
    assert len(plan.tasks) == 1
    assert plan.clarification_question is None


def test_clarification_plan_accepts_question_without_tasks():
    plan = QueryPlan(
        action=QueryPlanAction.NEEDS_CLARIFICATION,
        clarification_question=(
            "Which person are you asking about?"
        ),
    )

    assert plan.action == QueryPlanAction.NEEDS_CLARIFICATION
    assert plan.tasks == []


def test_clarification_plan_rejects_tasks():
    with pytest.raises(ValidationError):
        QueryPlan(
            action=QueryPlanAction.NEEDS_CLARIFICATION,
            clarification_question="Which person do you mean?",
            tasks=[
                PlannedTask(
                    type=TaskType.POLICY_DETAILS,
                    query="Find policy details",
                    evidence="policy",
                )
            ],
        )


def test_execute_plan_rejects_clarification_question():
    with pytest.raises(ValidationError):
        QueryPlan(
            action=QueryPlanAction.EXECUTE,
            tasks=[
                PlannedTask(
                    type=TaskType.POLICY_DETAILS,
                    query="Find policy details",
                    evidence="policy",
                )
            ],
            clarification_question="Which policy do you mean?",
        )
