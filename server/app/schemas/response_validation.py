from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


# ============================================================
# VALIDATION ACTIONS
# ============================================================


class ValidationAction(StrEnum):
    """
    What ChatService should do with the generated answer.
    """

    OK = "OK"
    REGENERATE = "REGENERATE"
    REJECT = "REJECT"
    HANDOFF = "HANDOFF"


# ============================================================
# GROUNDING VERDICTS
# ============================================================


class GroundingVerdict(StrEnum):
    """
    Result of semantic grounding validation.

    NOT_CHECKED means that semantic grounding validation
    was intentionally not executed.
    """

    NOT_CHECKED = "NOT_CHECKED"
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


# ============================================================
# VALIDATION ISSUE CODES
# ============================================================


class ValidationIssueCode(StrEnum):
    EMPTY_ANSWER = "EMPTY_ANSWER"
    NO_TRUSTED_EVIDENCE = "NO_TRUSTED_EVIDENCE"

    REGENERATION_LIMIT_EXCEEDED = (
        "REGENERATION_LIMIT_EXCEEDED"
    )

    INVALID_RUNTIME_STATE = "INVALID_RUNTIME_STATE"

    POLICY_FACT_MISMATCH = "POLICY_FACT_MISMATCH"

    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    CONTRADICTED_CLAIM = "CONTRADICTED_CLAIM"

    VALIDATOR_ERROR = "VALIDATOR_ERROR"


# ============================================================
# TRUSTED GROUNDING FACT
# ============================================================


class GroundingFact(BaseModel):
    """
    One trusted piece of evidence available
    to the grounding judge.

    Examples:

    id="policy.end_date"
    text="Policy end date: 2026-09-15"

    or:

    id="chunk:abc123"
    text="The insured person must notify the insurer..."
    """

    id: str = Field(
        min_length=1,
        max_length=200,
    )

    text: str = Field(
        min_length=1,
        max_length=10000,
    )


# ============================================================
# CLAIM-LEVEL GROUNDING RESULT
# ============================================================


class GroundingClaim(BaseModel):
    """
    One claim extracted from the generated answer
    and checked against trusted evidence.
    """

    # Example:
    # "Your policy expires on 15 September 2026."
    claim: str = Field(
        min_length=1,
        max_length=2000,
    )

    # Does this claim actually require evidence?
    #
    # Example:
    # "Your policy is active." -> True
    #
    # "Here is what I found:" -> False
    grounding_required: bool

    # Was this claim supported by trusted evidence?
    supported: bool

    # IDs of GroundingFact objects that support this claim.
    #
    # Example:
    # ["policy.end_date"]
    evidence_ids: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    # Optional secondary signal.
    #
    # We do NOT use this as the only safety gate.
    score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_claim(self):
        """
        Prevent impossible / suspicious states.

        If Model B says that a factual claim is supported,
        it must tell us which trusted evidence supports it.
        """

        if (
            self.grounding_required
            and self.supported
            and not self.evidence_ids
        ):
            raise ValueError(
                "Supported grounded claim must reference "
                "at least one evidence id."
            )

        return self


# ============================================================
# COMPLETE GROUNDING CHECK RESULT
# ============================================================


class GroundingCheckResult(BaseModel):
    """
    Structured result returned by the grounding judge
    after checking the complete draft answer.
    """

    verdict: GroundingVerdict

    # Overall score across the answer.
    #
    # Secondary signal / telemetry only.
    # Claim-level validation remains the main runtime gate.
    support_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    claims: list[GroundingClaim] = Field(
        default_factory=list,
        max_length=50,
    )

    @model_validator(mode="after")
    def validate_grounding_result(self):
        """
        Prevent contradictory grounding results.

        Example that must NOT be allowed:

        verdict = SUPPORTED

        but one factual claim has:
        supported = False
        """

        unsupported_required_claims = [
            claim
            for claim in self.claims
            if (
                claim.grounding_required
                and not claim.supported
            )
        ]

        if (
            self.verdict == GroundingVerdict.SUPPORTED
            and unsupported_required_claims
        ):
            raise ValueError(
                "SUPPORTED grounding result cannot contain "
                "unsupported required claims."
            )

        return self


# ============================================================
# VALIDATION ISSUE
# ============================================================


class ValidationIssue(BaseModel):
    """
    One concrete problem found during validation.
    """

    code: ValidationIssueCode

    message: str = Field(
        min_length=1,
        max_length=1000,
    )

    # Specific sentence / factual claim
    # from the generated answer.
    claim: str | None = None

    # Evidence relevant to this issue.
    #
    # Example:
    # ["policy.end_date"]
    evidence: list[str] = Field(
        default_factory=list,
        max_length=10,
    )


# ============================================================
# FINAL RESPONSE VALIDATION RESULT
# ============================================================


class ValidationResult(BaseModel):
    """
    Final decision returned by ResponseValidator.

    This is the result ChatService will eventually use
    to decide what happens to the generated answer.
    """

    action: ValidationAction

    grounding: GroundingVerdict = (
        GroundingVerdict.NOT_CHECKED
    )

    issues: list[ValidationIssue] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_result(self):
        """
        Protect the backend from contradictory states.
        """

        # We cannot release an answer when semantic grounding
        # already tells us that it failed.
        if (
            self.action == ValidationAction.OK
            and self.grounding
            in {
                GroundingVerdict.UNSUPPORTED,
                GroundingVerdict.CONTRADICTED,
            }
        ):
            raise ValueError(
                "Validation action cannot be OK when "
                "grounding is UNSUPPORTED or CONTRADICTED."
            )

        # Any non-OK decision must explain what went wrong.
        if (
            self.action != ValidationAction.OK
            and not self.issues
        ):
            raise ValueError(
                "Non-OK validation result must contain "
                "at least one validation issue."
            )

        return self