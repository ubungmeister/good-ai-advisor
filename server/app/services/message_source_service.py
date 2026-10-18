import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.message_source_repository import (
    MessageSourceRepository,
)
from app.schemas.task_result import (
    RetrievalTaskContent,
    TaskResult,
)
from app.schemas.task_routing import TaskTarget


class MessageSourceService:

    def __init__(self):
        self.message_source_repository = (
            MessageSourceRepository()
        )

    def save_from_task_results(
        self,
        *,
        db: Session,
        message_id: uuid.UUID,
        task_results: list[TaskResult],
    ) -> None:

        for result in task_results:

            if result.target != TaskTarget.RETRIEVAL:
                continue

            if not isinstance(
                result.content,
                RetrievalTaskContent,
            ):
                continue

            for chunk in result.content.chunks:

                self.message_source_repository.create(
                    db=db,
                    message_id=message_id,
                    source_type="DOCUMENT_CHUNK",
                    document_chunk_id=chunk.id,
                    relevance_score=Decimal(
                        str(chunk.score)
                    ),
                )

        db.commit()