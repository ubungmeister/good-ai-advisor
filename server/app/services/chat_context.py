
import json
from collections.abc import Sequence

from app.models import ConversationRole
from app.models.message import Message

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
