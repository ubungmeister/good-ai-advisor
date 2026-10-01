from enum import StrEnum

from pydantic import BaseModel, Field


class TaskType(StrEnum):
    GENERAL_QUESTION = "GENERAL_QUESTION"
    COVERAGE_CHECK = "COVERAGE_CHECK"
    PROCEDURE = "PROCEDURE"
    POLICY_DETAILS = "POLICY_DETAILS"


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
    tasks: list[PlannedTask] = Field(
        min_length=1,
        max_length=5,
    )