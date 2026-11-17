import uuid
from collections.abc import Sequence

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import ConversationRole, Message
from app.services.access_errors import ResourceNotFoundError
from app.services.policy_service import PolicyService



class ConversationService:

    def __init__(self):
        self.conversation_repository = ConversationRepository()
        self.message_repository = MessageRepository()
        self.policy_service = PolicyService()

    def get_or_create(
        self,
        *,
        db: Session,
        user_id: uuid.UUID,
        policy_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> Conversation:

        if conversation_id is not None:

            conversation = (
                self.conversation_repository.get_by_id_for_user(
                    db=db,
                    conversation_id=conversation_id,
                    user_id=user_id,
                )
            )

            if conversation is None:
                raise ResourceNotFoundError(
                    "Conversation was not found "
                    "or does not belong to the user."
                )

            # A continuation keeps the original policy; switching requires a new chat.
            if policy_id is not None and policy_id != conversation.policy_id:
                raise ResourceNotFoundError("Conversation not found.")
            self._check_policy(db=db, user_id=user_id, policy_id=conversation.policy_id)
            return conversation

        self._check_policy(db=db, user_id=user_id, policy_id=policy_id)

        conversation = self.conversation_repository.create(
            db=db,
            user_id=user_id,
            policy_id=policy_id,
        )

        db.commit()
        db.refresh(conversation)

        return conversation

    def _check_policy(
        self, *, db: Session, user_id: uuid.UUID, policy_id: uuid.UUID | None,
    ) -> None:
        if policy_id is not None and self.policy_service.get_policy_for_user(
            db=db, policy_id=policy_id, user_id=user_id,
        ) is None:
            raise ResourceNotFoundError("Policy not found.")

    def add_message(
        self,
        *,
        db: Session,
        conversation_id: uuid.UUID,
        role: ConversationRole,
        content: str,
    ) -> Message:

        message = self.message_repository.create(
            db=db,
            conversation_id=conversation_id,
            role=role,
            content=content,
        )

        db.commit()
        db.refresh(message)

        return message

    def get_messages(
        self,
        *,
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Sequence[Message]:

        conversation = (
            self.conversation_repository.get_by_id_for_user(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
            )
        )

        if conversation is None:
            raise ValueError(
                "Conversation was not found "
                "or does not belong to the user."
            )

        return self.message_repository.get_by_conversation(
            db=db,
            conversation_id=conversation_id,
        )

    def get_user_conversations(
        self,
        *,
        db: Session,
        user_id: uuid.UUID,
    ) -> Sequence[Conversation]:

        return self.conversation_repository.get_by_user(
            db=db,
            user_id=user_id,
        )

    def get_recent_messages(
        self,
        *,
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> Sequence[Message]:
        conversation = (
            self.conversation_repository.get_by_id_for_user(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
            )
        )

        if conversation is None:
            raise ValueError(
                "Conversation was not found "
                "or does not belong to the user."
            )

        return self.message_repository.get_recent_by_conversation(
            db=db,
            conversation_id=conversation_id,
            limit=limit,
        )
