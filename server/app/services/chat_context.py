
import json
from collections.abc import Sequence

from app.models import ConversationRole
from app.models.message import Message
from app.schemas.response_validation import ValidationResult

DEFAULT_CONVERSATION_CONTEXT_MESSAGE_LIMIT = 10


def format_conversation_history(
    *,
    messages: Sequence[Message],
) -> str:
    # Keep the existing plain-text format for current LLM calls.
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


def format_conversation_context(
    *,
    messages: Sequence[Message],
) -> str:
    """Format conversation messages for the future resolver."""
    context_messages = []

    for message in messages:
        if message.role not in {
            ConversationRole.USER,
            ConversationRole.ASSISTANT,
        }:
            continue

        context_messages.append(
            {
                "message_id": str(message.id),
                "role": message.role.value,
                "created_at": message.created_at.isoformat(),
                "content": message.content,
            }
        )

    if not context_messages:
        return ""

    return json.dumps(
        context_messages,
        ensure_ascii=False,
        indent=2,
    )



def build_answer_context(
    *,
    trusted_context: str,
    conversation_history: str,
) -> str:
    """Combine trusted evidence with history used only for interpretation."""

    sections = [
        "[TRUSTED INSURANCE EVIDENCE]\n"
        f"{trusted_context.strip()}"
    ]

    if conversation_history.strip():
        sections.append(
            "[CONVERSATION HISTORY — CONTEXT ONLY, "
            "NOT FACTUAL EVIDENCE]\n"
            f"{conversation_history.strip()}"
        )

    return "\n\n".join(sections)

def build_regeneration_context(
    *,
    trusted_context: str,
    conversation_history: str,
    previous_answer: str,
    validation: ValidationResult,
) -> str:
    """Build context for regenerating an answer after validation fails."""

    sections = [
        build_answer_context(
            trusted_context=trusted_context,
            conversation_history=conversation_history,
        )
    ]

    sections.append(
        "[PREVIOUS DRAFT — UNVERIFIED]\n"
        "This answer failed validation. Do not assume its claims "
        "are correct; use it only to identify what needs correction.\n"
        f"{previous_answer.strip()}"
    )

    validation_json = json.dumps(
        validation.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )

    sections.append(
        "[VALIDATION FEEDBACK]\n"
        "Use this result to identify and correct the previous draft. "
        "The trusted insurance evidence above remains the source "
        "of factual claims.\n"
        f"{validation_json}"
    )

    return "\n\n".join(sections)