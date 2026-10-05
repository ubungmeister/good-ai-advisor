from enum import StrEnum

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class ValidationAction(StrEnum):
    OK = "OK"
    REGENERATE = "REGENERATE"
    REJECT = "REJECT"
    HANDOFF = "HANDOFF"


class ResponseValidation(BaseModel):
    action: ValidationAction

    issues: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    @model_validator(mode="after")
    def validate_result(self):
        if self.action == ValidationAction.OK:
            if self.issues:
                raise ValueError(
                    "OK validation must not contain issues."
                )

        else:
            if not self.issues:
                raise ValueError(
                    "Non-OK validation must contain "
                    "at least one issue."
                )

        return self