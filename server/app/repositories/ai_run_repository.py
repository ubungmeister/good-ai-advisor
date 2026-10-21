import uuid

from sqlalchemy.orm import Session

from app.models.ai_run import AiRun


class AiRunRepository:

    def create(
        self,
        *,
        db: Session,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        latency_ms: int | None = None,
        retrieval_count: int | None = None,
        safety_result: str | None = None,
    ) -> AiRun:

        ai_run = AiRun(
            conversation_id=conversation_id,
            message_id=message_id,
            latency_ms=latency_ms,
            retrieval_count=retrieval_count,
            safety_result=safety_result,
        )

        db.add(ai_run)
        db.flush()

        return ai_run