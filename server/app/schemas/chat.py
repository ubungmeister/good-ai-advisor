import uuid

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str

    # Temporary development version.
    # Later user_id will come from authentication.
    user_id: uuid.UUID | None = None

    # Policy selected by the user in the UI.
    policy_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    answer: str