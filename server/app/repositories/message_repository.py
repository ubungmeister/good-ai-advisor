import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import ConversationRole, Message


class MessageRepository:

    def create(
        self,
        *,
        db: Session,
        conversation_id: uuid.UUID,
        role: ConversationRole,
        content: str,
    ) -> Message:

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )

        db.add(message)
        db.flush()

        return message

    def get_by_conversation(
        self,
        *,
        db: Session,
        conversation_id: uuid.UUID,
    ) -> Sequence[Message]:

        return db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
            )
            .order_by(
                Message.created_at.asc(),
            )
        ).all()

    def get_recent_by_conversation(
        self,
        *,
        db: Session,
        conversation_id: uuid.UUID,
        limit: int = 10,
    ) -> Sequence[Message]:
        if limit < 1:
            raise ValueError("Message limit must be positive.")

        messages = list(
            db.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                )
                .order_by(
                    Message.created_at.desc(),
                    Message.id.desc(),
                )
                .limit(limit)
            ).all()
        )

        # The database returns newest first. Restore chronological order.
        messages.reverse()

        return messages

