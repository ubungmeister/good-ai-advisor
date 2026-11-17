import uuid

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str

    # None starts a new conversation.
    # An existing ID continues that conversation.
    conversation_id: uuid.UUID | None = None

    # Policy selected by the user in the UI.
    policy_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: uuid.UUID
