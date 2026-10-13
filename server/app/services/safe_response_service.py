from app.schemas.response_validation import ValidationAction


class SafeResponseService:
    """
    Builds safe user-facing responses when an AI-generated
    answer cannot be released.

    This service does not decide whether an answer is valid.
    That responsibility belongs to ResponseValidator.

    It only translates a validation decision into a safe
    response for the user.
    """

    HANDOFF_MESSAGE = (
        "I could not reliably verify the answer from the "
        "available trusted insurance information. "
        "Please check your policy documentation or "
        "contact support."
    )

    REJECT_MESSAGE = (
        "I cannot provide a reliable answer to this question "
        "from the available insurance information. "
        "Please contact support if you need assistance."
    )

    DEFAULT_MESSAGE = (
        "I could not provide a sufficiently reliable answer. "
        "Please check your policy documentation or "
        "contact support."
    )

    def build(
        self,
        *,
        action: ValidationAction,
    ) -> str:

        if action == ValidationAction.HANDOFF:
            return self.HANDOFF_MESSAGE

        if action == ValidationAction.REJECT:
            return self.REJECT_MESSAGE

        return self.DEFAULT_MESSAGE