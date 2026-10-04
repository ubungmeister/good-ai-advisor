from pydantic import BaseModel, Field

from app.schemas.query_plan import TaskType
from app.schemas.task_routing import TaskTarget


class TaskResult(BaseModel):
    task_type: TaskType
    target: TaskTarget

    content: str = Field(
        min_length=1,
    )