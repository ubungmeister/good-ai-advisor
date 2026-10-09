from collections.abc import Sequence

from app.schemas.response_validation import (
    GroundingCheckResult,
    GroundingFact,
    GroundingVerdict,
)
from app.services.llm_service import LLMService


class GroundingValidator:
    """
    Semantic grounding validator.

    Uses Model B to check whether factual claims
    in Model A's draft answer are supported by
    trusted evidence.

    Model B performs semantic reasoning.

    Python validates:
    - returned schema
    - evidence IDs
    - basic result invariants
    """

    def __init__(
        self,
        *,
        llm_service: LLMService,
    ):
        self.llm_service = llm_service

    async def validate(
        self,
        *,
        question: str,
        draft_answer: str,
        facts: Sequence[GroundingFact],
    ) -> GroundingCheckResult:

        if not draft_answer.strip():
            raise ValueError(
                "Draft answer cannot be empty."
            )

        if not facts:
            raise ValueError(
                "Grounding validation requires "
                "trusted evidence."
            )

        context = self._build_context(
            draft_answer=draft_answer,
            facts=facts,
        )

        result = (
            await self.llm_service.generate_structured(
                system_prompt=self._system_prompt(),
                user_message=question,
                context=context,
                response_model=GroundingCheckResult,
            )
        )

        self._validate_result(
            result=result,
            facts=facts,
        )

        return result

    # ========================================================
    # MODEL B PROMPT
    # ========================================================

    def _system_prompt(self) -> str:
        return """
You are a factual grounding validator for an insurance assistant.

Your task is NOT to answer the user's question.

Your task is to evaluate the DRAFT ANSWER against
the supplied TRUSTED EVIDENCE.

For each meaningful factual claim in the draft:

1. Extract the claim.
2. Decide whether the claim requires grounding.
3. If grounding is required, determine whether the claim
   is supported by the trusted evidence.
4. Return the exact evidence IDs relevant to the claim.

A factual insurance or policy statement normally requires
grounding.

Conversational or purely stylistic text does not require
grounding.

Choose the overall verdict using these rules:

SUPPORTED:
Every material factual claim that requires grounding is
supported by the supplied trusted evidence.

UNSUPPORTED:
At least one material factual claim is not established
by the supplied trusted evidence.

CONTRADICTED:
At least one material factual claim directly conflicts
with the supplied trusted evidence.

Do NOT use NOT_CHECKED.
NOT_CHECKED is reserved for backend flows where semantic
grounding validation was intentionally not executed.

Important rules:

- Use only TRUSTED EVIDENCE supplied in the context.
- Do not use outside knowledge.
- Do not assume missing information.
- Do not invent insurance facts.
- Do not invent evidence IDs.
- Evidence IDs must exactly match IDs supplied in
  TRUSTED EVIDENCE.
- Different wording may express the same factual meaning.
- Different formatting of the same value does not make
  a claim unsupported.
- If evidence directly contradicts a claim, mark the
  claim as unsupported and include the conflicting
  evidence ID.
- If evidence simply does not establish a claim,
  mark it as unsupported.
- Do not generate a new answer for the user.

For the current implementation:
- set support_score to null
- set every claim score to null

Confidence scores are not used by the runtime yet.
"""

    # ========================================================
    # MODEL B CONTEXT
    # ========================================================

    def _build_context(
        self,
        *,
        draft_answer: str,
        facts: Sequence[GroundingFact],
    ) -> str:

        evidence = "\n\n".join(
            (
                f"[{fact.id}]\n"
                f"{fact.text}"
            )
            for fact in facts
        )

        return (
            "[DRAFT ANSWER]\n"
            f"{draft_answer}\n\n"
            "[TRUSTED EVIDENCE]\n"
            f"{evidence}"
        )

    # ========================================================
    # BACKEND VALIDATION
    # ========================================================

    def _validate_result(
        self,
        *,
        result: GroundingCheckResult,
        facts: Sequence[GroundingFact],
    ) -> None:

        allowed_ids = {
            fact.id
            for fact in facts
        }

        # Model B is not allowed to invent evidence IDs.
        for claim in result.claims:

            for evidence_id in claim.evidence_ids:

                if evidence_id not in allowed_ids:
                    raise ValueError(
                        "Grounding validator returned "
                        "an unknown evidence ID: "
                        f"{evidence_id}"
                    )

        required_unsupported_claims = [
            claim
            for claim in result.claims
            if (
                claim.grounding_required
                and not claim.supported
            )
        ]

        # NOT_CHECKED belongs to backend routing,
        # not to Model B.
        if (
            result.verdict
            == GroundingVerdict.NOT_CHECKED
        ):
            raise ValueError(
                "Model B cannot return NOT_CHECKED."
            )

        # Pydantic already protects the main SUPPORTED
        # invariant, but keeping this here makes the
        # service contract explicit.
        if (
            result.verdict
            == GroundingVerdict.SUPPORTED
            and required_unsupported_claims
        ):
            raise ValueError(
                "SUPPORTED result contains "
                "unsupported grounded claims."
            )

        if (
            result.verdict
            == GroundingVerdict.UNSUPPORTED
            and not required_unsupported_claims
        ):
            raise ValueError(
                "UNSUPPORTED result must contain "
                "at least one unsupported "
                "grounded claim."
            )

        if (
            result.verdict
            == GroundingVerdict.CONTRADICTED
        ):
            contradicted_claims_with_evidence = [
                claim
                for claim
                in required_unsupported_claims
                if claim.evidence_ids
            ]

            if not contradicted_claims_with_evidence:
                raise ValueError(
                    "CONTRADICTED result must reference "
                    "conflicting trusted evidence."
                )