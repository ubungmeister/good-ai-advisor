from enum import StrEnum

from pydantic import BaseModel

from app.schemas.query_plan import PlannedTask


class TaskTarget(StrEnum):
    RETRIEVAL = "RETRIEVAL"
    POLICY = "POLICY"


class RoutedTask(BaseModel):
    task: PlannedTask
    targets: list[TaskTarget]