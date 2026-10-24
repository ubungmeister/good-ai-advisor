import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation


class ConversationRepository:

    def create(
        self,
        *,
        db: Session,
        user_id: uuid.UUID,
        policy_id: uuid.UUID | None = None,
    ) -> Conversation:

        conversation = Conversation(
            user_id=user_id,
            policy_id=policy_id,
        )

        db.add(conversation)
        db.flush()

        return conversation

    def get_by_id_for_user(
        self,
        *,
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Conversation | None:

        return db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )

    def get_by_user(
        self,
        *,
        db: Session,
        user_id: uuid.UUID,
    ) -> Sequence[Conversation]:

        return db.scalars(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
            )
            .order_by(
                Conversation.created_at.desc(),
            )
        ).all()
