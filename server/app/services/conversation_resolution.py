
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ConversationResolutionAction(StrEnum):
    NEW_REQUEST = "NEW_REQUEST"
    RESOLVED_FOLLOW_UP = "RESOLVED_FOLLOW_UP"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


class ConversationResolution(BaseModel):
    action: ConversationResolutionAction

    resolved_request: str | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
    )

    referenced_message_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=10,
    )

    clarification_question: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_resolution(self):
        if self.action == ConversationResolutionAction.NEW_REQUEST:
            if (
                self.resolved_request is not None
                or self.referenced_message_ids
                or self.clarification_question is not None
            ):
                raise ValueError(
                    "NEW_REQUEST must not contain "
                    "resolved follow-up fields."
                )

        elif self.action == ConversationResolutionAction.RESOLVED_FOLLOW_UP:
            if not self.resolved_request:
                raise ValueError(
                    "RESOLVED_FOLLOW_UP requires resolved_request."
                )

            if not self.referenced_message_ids:
                raise ValueError(
                    "RESOLVED_FOLLOW_UP requires message references."
                )

            if self.clarification_question is not None:
                raise ValueError(
                    "RESOLVED_FOLLOW_UP must not contain "
                    "a clarification question."
                )

        elif self.action == ConversationResolutionAction.NEEDS_CLARIFICATION:
            if not self.clarification_question:
                raise ValueError(
                    "NEEDS_CLARIFICATION requires "
                    "clarification_question."
                )

            if self.resolved_request is not None:
                raise ValueError(
                    "NEEDS_CLARIFICATION must not contain "
                    "resolved_request."
                )

        return self
