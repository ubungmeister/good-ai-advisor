import uuid

from sqlalchemy.orm import Session

from app.repositories.ai_run_repository import AiRunRepository
from app.schemas.task_result import (
    RetrievalTaskContent,
    TaskResult,
)
from app.schemas.task_routing import TaskTarget


class AiRunService:

    def __init__(self):
        self.ai_run_repository = AiRunRepository()

    def save_run(
        self,
        *,
        db: Session,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        latency_ms: int,
        safety_result: str,
        task_results: list[TaskResult] | None = None,
    ) -> None:

        retrieval_count = 0

        if task_results:
            for result in task_results:

                if (
                    result.target == TaskTarget.RETRIEVAL
                    and isinstance(
                        result.content,
                        RetrievalTaskContent,
                    )
                ):
                    retrieval_count += len(
                        result.content.chunks
                    )

        self.ai_run_repository.create(
            db=db,
            conversation_id=conversation_id,
            message_id=message_id,
            latency_ms=latency_ms,
            retrieval_count=retrieval_count,
            safety_result=safety_result,
        )

        db.commit()