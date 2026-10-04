from pydantic import BaseModel, Field

from app.schemas.query_plan import TaskType
from app.schemas.task_routing import TaskTarget


class TaskResult(BaseModel):
    """
    Result produced by one routed task target.

    ChatService collects these results and passes
    them to ContextBuilder.
    """

    task_type: TaskType
    target: TaskTarget

    content: str = Field(
        min_length=1,
    )