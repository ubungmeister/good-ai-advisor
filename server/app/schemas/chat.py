import uuid

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str

    # None starts a new conversation.
    # An existing ID continues that conversation.
    conversation_id: uuid.UUID | None = None

    # Temporary development values.
    # Later, user_id will come from authentication.
    user_id: uuid.UUID | None = None

    # Policy selected by the user in the UI.
    policy_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: uuid.UUID