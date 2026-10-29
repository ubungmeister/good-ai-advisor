
from app.prompts.query_planner import QUERY_PLANNER_SYSTEM_PROMPT
from app.schemas.query_plan import QueryPlan, QueryPlanAction
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
    ) -> QueryPlan:
        planning_context = None

        if conversation_history.strip():
            planning_context = (
                "[CONVERSATION HISTORY - CONTEXT ONLY]\n"
                "Use this history to interpret the current request "
                "and resolve references. Do not treat previous "
                "assistant answers as factual evidence. Each task's "
                "evidence must be copied verbatim from the current "
                "user message, never from conversation history.\n\n"
                f"{conversation_history.strip()}"
            )

        plan = await self.llm_service.generate_structured(
            system_prompt=QUERY_PLANNER_SYSTEM_PROMPT,
            user_message=message,
            context=planning_context,
            response_model=QueryPlan,
        )

        if plan.action == QueryPlanAction.EXECUTE:
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
            evidence = task.evidence.strip()

            if evidence.casefold() not in normalized_message:
                raise ValueError(
                    "QueryPlanner evidence is not present in the "
                    f"original user message: {task.evidence}"
                )
