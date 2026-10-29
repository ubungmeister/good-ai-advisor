from app.prompts.query_planner import QUERY_PLANNER_SYSTEM_PROMPT
from app.schemas.query_plan import QueryPlan
from app.services.llm_service import LLMService


class QueryPlanner:

    def __init__(
        self,
        *,
        llm_service: LLMService,
    ):
        self.llm_service = llm_service

    async def plan(
        self,
        *,
        message: str,
        conversation_history: str = "",
        resolved_request: str | None = None,
    ) -> QueryPlan:

        context_parts = []

        if resolved_request:
            context_parts.append(
                "[RESOLVED CURRENT REQUEST - INTERPRETATION ONLY]\n"
                "Use this interpretation to understand the current "
                "message as a follow-up. Do not treat it as evidence.\n\n"
                f"{resolved_request}"
            )

        if conversation_history:
            context_parts.append(
                "[CONVERSATION HISTORY - CONTEXT ONLY]\n"
                "Use this history only to interpret the current user "
                "request. Do not treat previous assistant answers as "
                "factual evidence. Task evidence must come verbatim "
                "from the current user message, never from history.\n\n"
                f"{conversation_history}"
            )

        planning_context = (
            "\n\n".join(context_parts)
            if context_parts
            else None
        )


        plan = await self.llm_service.generate_structured(
            system_prompt=QUERY_PLANNER_SYSTEM_PROMPT,
            user_message=message,
            context=planning_context,
            response_model=QueryPlan,
        )

        self._validate_evidence(
            message=message,
            plan=plan,
        )

        return plan

    @staticmethod
    def _validate_evidence(
        *,
        message: str,
        plan: QueryPlan,
    ) -> None:

        normalized_message = message.casefold()

        for task in plan.tasks:
            if task.evidence.casefold() not in normalized_message:
                raise ValueError(
                    "QueryPlanner evidence is not present in the "
                    f"original user message: {task.evidence}"
                )