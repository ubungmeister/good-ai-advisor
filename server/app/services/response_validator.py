from app.schemas.response_validation import (
    ResponseValidation,
)
from app.services.llm_service import LLMService


class ResponseValidator:

    def __init__(
        self,
        *,
        llm_service: LLMService,
    ):
        self.llm_service = llm_service

    async def validate(
        self,
        *,
        user_message: str,
        draft_answer: str,
        trusted_context: str,
    ) -> ResponseValidation:

        system_prompt = """
You are a response validator for an insurance assistant.

Your job is NOT to answer the user.

Your job is to verify whether the draft answer is grounded
in the trusted context.

The trusted context is the only source of truth.

Check especially:
- dates
- numbers
- currencies
- policy status
- payment status
- coverage
- coverage limits
- selected options
- exclusions
- insurance procedures
- who must do what
- any other factual claim

Rules:

1. Return OK only when every material factual claim in the
   draft answer is supported by the trusted context.

2. Translation, formatting, summarization and natural
   wording are allowed if the factual meaning is preserved.

3. Return REGENERATE when the trusted context contains enough
   information to answer correctly, but the draft contains
   an incorrect, contradictory or unsupported factual claim.

4. Return REJECT when the trusted context does not contain
   enough information to support the answer.

5. Return HANDOFF only when the request requires a human
   decision or action that cannot be safely completed from
   the trusted context.

6. Do not invent facts while validating.

7. issues must contain short, concrete explanations of the
   validation problem.

8. If action is OK, issues must be empty.
"""

        validation_input = f"""
USER MESSAGE:
{user_message}

DRAFT ANSWER:
{draft_answer}

TRUSTED CONTEXT:
{trusted_context}
"""

        return await self.llm_service.generate_structured(
            system_prompt=system_prompt,
            user_message=validation_input,
            response_model=ResponseValidation,
        )