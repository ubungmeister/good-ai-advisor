
from collections.abc import Sequence

from app.models import ConversationRole
from app.models.message import Message


def format_conversation_history(
    *,
    messages: Sequence[Message],
) -> str:
    # Keep the prompt bounded to the latest 10 messages.
    recent_messages = messages[-10:]

    lines: list[str] = []

    for message in recent_messages:
        if message.role == ConversationRole.USER:
            speaker = "User"
        elif message.role == ConversationRole.ASSISTANT:
            speaker = "Assistant"
        else:
            continue

        lines.append(f"{speaker}: {message.content}")

    return "\n".join(lines)


def build_answer_context(
    *,
    trusted_context: str,
    conversation_history: str,
) -> str:
    if not conversation_history:
        return trusted_context

    return (
        f"{trusted_context}\n\n"
        "[CONVERSATION HISTORY - CONTEXT ONLY, "
        "NOT TRUSTED EVIDENCE]\n"
        f"{conversation_history}"
    )


def build_regeneration_context(
    *,
    trusted_context: str,
    conversation_history: str,
    previous_answer: str,
    validation,
) -> str:
    feedback_lines: list[str] = []

    for issue in validation.issues:
        feedback_lines.append(
            f"- {issue.code.value}: {issue.message}"
        )

        if issue.claim:
            feedback_lines.append(
                f"  Problematic claim: {issue.claim}"
            )

        if issue.evidence:
            feedback_lines.append(
                "  Relevant evidence IDs: "
                + ", ".join(issue.evidence)
            )

    feedback = "\n".join(feedback_lines)

    return f"""
[TRUSTED INSURANCE CONTEXT]

{trusted_context}

[CONVERSATION HISTORY - CONTEXT ONLY, NOT TRUSTED EVIDENCE]

{conversation_history}

[PREVIOUS DRAFT - NOT TRUSTED EVIDENCE]

{previous_answer}

[VALIDATION FEEDBACK]

{feedback}

Generate a corrected answer.

Rules:
- Use only TRUSTED INSURANCE CONTEXT as factual evidence.
- Use conversation history only to interpret the current request.
- Correct the problems identified in VALIDATION FEEDBACK.
- Do not treat the previous draft as evidence.
- Do not invent missing insurance facts.
- Keep the answer focused on the user's original question.
"""
