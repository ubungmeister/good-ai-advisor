from collections.abc import Sequence
from time import perf_counter

from app.prompts.grounding_validator import GROUNDING_VALIDATOR_SYSTEM_PROMPT
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

        # Before the Model B call
        model_b_started = perf_counter()

        result = await self.llm_service.generate_structured(
            system_prompt=GROUNDING_VALIDATOR_SYSTEM_PROMPT,
            user_message=question,
            context=context,
            response_model=GroundingCheckResult,
            strict=True,
        )

        print(
            f"MODEL B LATENCY: "
            f"{perf_counter() - model_b_started:.2f}s"
        )

        print("\nMODEL B STRUCTURED RESULT:")
        print(result.model_dump_json(indent=2))

        # Continue with normalization and backend validation
        result = self._normalize_evidence_ids(
            result=result,
            facts=facts,
        )

        # # Normalize evidence IDs returned by Model B.
        # result = self._normalize_evidence_ids(
        #     result=result,
        #     facts=facts,
        # )

        if not result.claims:
            raise ValueError(
                "Grounding validator returned no claims."
            )

        # Validate the normalized result.
        self._validate_result(
            result=result,
            facts=facts,
        )

        return result


    # ========================================================
    # MODEL B PROMPT
    # ========================================================

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
                f"Evidence ID: {fact.id}\n"
                f"Evidence text: {fact.text}"
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


    @staticmethod
    def _normalize_evidence_ids(
            *,
            result: GroundingCheckResult,
            facts: Sequence[GroundingFact],
    ) -> GroundingCheckResult:

        allowed_ids = {
            fact.id
            for fact in facts
        }

        for claim in result.claims:
            normalized_ids = []

            for evidence_id in claim.evidence_ids:
                normalized_id = evidence_id.strip()

                # Handle a single pair of surrounding brackets.
                if (
                        normalized_id.startswith("[")
                        and normalized_id.endswith("]")
                ):
                    normalized_id = normalized_id[1:-1].strip()

                normalized_ids.append(normalized_id)

            claim.evidence_ids = list(
                dict.fromkeys(normalized_ids)
            )

        return result