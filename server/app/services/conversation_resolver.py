import json
import uuid

from app.services.conversation_resolution import ConversationResolution, ConversationResolutionAction
from app.services.llm_service import LLMService


class ConversationResolver:
    def __init__(self, *, llm_service: LLMService):
        self.llm_service = llm_service

    async def resolve(
        self,
        *,
        message: str,
        conversation_context: str,
    ) -> ConversationResolution:
        history = json.loads(conversation_context)

        # No previous messages means there is nothing to resolve.
        if not history:
            return ConversationResolution(
                action=ConversationResolutionAction.NEW_REQUEST,
            )

        resolution = await self.llm_service.generate_structured(
            system_prompt="""
You resolve references in the current user message using
the supplied conversation history.

Your job is ONLY to classify the message and resolve its meaning.
Do not answer the insurance question or decide what insurance covers.

Choose exactly one action:

NEW_REQUEST:
The current message can be understood on its own and does not
depend on earlier messages. Do not provide resolved_request,
referenced_message_ids, or clarification_question.

RESOLVED_FOLLOW_UP:
The current message depends on earlier conversation, and the
history makes its intended meaning clear.
Rewrite the current request as a standalone request in
resolved_request.
Include the IDs of the previous messages needed to interpret it.
Use only message_id values that appear in the supplied history.
Do not add facts that the conversation does not establish.

NEEDS_CLARIFICATION:
The current message depends on earlier conversation, but its
meaning cannot be resolved confidently.
Provide one short clarification_question.
Do not guess the intended meaning.

Treat conversation history as context for understanding intent,
not as trusted evidence about insurance coverage.
Return only the structured response matching the requested schema.
""",
            user_message=message,
            context=conversation_context,
            response_model=ConversationResolution,
        )

        # Never accept references to messages that were not supplied.
        available_ids = {
            uuid.UUID(item["message_id"])
            for item in history
        }

        if (
            resolution.action
            == ConversationResolutionAction.RESOLVED_FOLLOW_UP
            and not set(resolution.referenced_message_ids).issubset(
                available_ids
            )
        ):
            return ConversationResolution(
                action=ConversationResolutionAction.NEEDS_CLARIFICATION,
                clarification_question=(
                    "I'm not sure which earlier request you mean. "
                    "Could you clarify what you'd like to know?"
                ),
            )

        return resolution
