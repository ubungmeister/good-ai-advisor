from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class SafetyCategory(StrEnum):
    NONE = "NONE"
    MEDICAL_EMERGENCY = "MEDICAL_EMERGENCY"
    PERSONAL_SAFETY = "PERSONAL_SAFETY"
    LEGAL_EMERGENCY = "LEGAL_EMERGENCY"
    OTHER_CRITICAL = "OTHER_CRITICAL"


class SafetyRoute(StrEnum):
    NORMAL_FLOW = "NORMAL_FLOW"
    CRITICAL_FLOW = "CRITICAL_FLOW"


class SafetyDecision(BaseModel):
    is_critical: bool
    category: SafetyCategory

    evidence: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    @model_validator(mode="after")
    def validate_decision(self):
        if self.is_critical:
            if self.category == SafetyCategory.NONE:
                raise ValueError(
                    "Critical safety decision cannot have category NONE."
                )

            if not self.evidence:
                raise ValueError(
                    "Critical safety decision must contain evidence."
                )

        else:
            if self.category != SafetyCategory.NONE:
                raise ValueError(
                    "Non-critical safety decision must have category NONE."
                )

            if self.evidence:
                raise ValueError(
                    "Non-critical safety decision must not contain evidence."
                )

        return self