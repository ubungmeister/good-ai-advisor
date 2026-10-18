import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.message_source import MessageSource


class MessageSourceRepository:

    def create(
        self,
        *,
        db: Session,
        message_id: uuid.UUID,
        source_type: str,
        document_chunk_id: uuid.UUID | None = None,
        policy_coverage_id: uuid.UUID | None = None,
        policy_option_id: uuid.UUID | None = None,
        relevance_score: Decimal | None = None,
    ) -> MessageSource:

        message_source = MessageSource(
            message_id=message_id,
            source_type=source_type,
            document_chunk_id=document_chunk_id,
            policy_coverage_id=policy_coverage_id,
            policy_option_id=policy_option_id,
            relevance_score=relevance_score,
        )

        db.add(message_source)
        db.flush()

        return message_source