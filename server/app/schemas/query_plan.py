
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class TaskType(StrEnum):
    GENERAL_QUESTION = "GENERAL_QUESTION"
    COVERAGE_CHECK = "COVERAGE_CHECK"
    PROCEDURE = "PROCEDURE"
    POLICY_DETAILS = "POLICY_DETAILS"


class QueryPlanAction(StrEnum):
    EXECUTE = "EXECUTE"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


class PlannedTask(BaseModel):
    type: TaskType

    query: str = Field(
        min_length=1,
        max_length=500,
    )

    evidence: str = Field(
        min_length=1,
        max_length=500,
    )


class QueryPlan(BaseModel):
    action: QueryPlanAction

    tasks: list[PlannedTask] = Field(
        default_factory=list,
        max_length=5,
    )

    clarification_question: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_plan(self):
        if self.action == QueryPlanAction.EXECUTE:
            if not self.tasks:
                raise ValueError(
                    "EXECUTE requires at least one task."
                )

            if self.clarification_question is not None:
                raise ValueError(
                    "EXECUTE must not contain a clarification question."
                )

        elif self.action == QueryPlanAction.NEEDS_CLARIFICATION:
            if not self.clarification_question:
                raise ValueError(
                    "NEEDS_CLARIFICATION requires a clarification question."
                )

            if self.tasks:
                raise ValueError(
                    "NEEDS_CLARIFICATION must not contain tasks."
                )

        return self
