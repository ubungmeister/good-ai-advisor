import time

from app.prompts.query_planner import QUERY_PLANNER_SYSTEM_PROMPT
from app.schemas.query_plan import QueryPlan, QueryPlanAction
from app.services.llm_service import LLMService
from app.core.config import settings


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
            system_prompt=(
                QUERY_PLANNER_SYSTEM_PROMPT
                + "\n# CORPUS SEARCH LANGUAGE\n"
                + f"Write every task.query in {settings.retrieval_query_language}, the indexed corpus language. "
                + "Translate the meaning faithfully; preserve entities, amounts, dates and distinctions "
                  "such as baggage delay versus flight delay. Do not add coverage assumptions. "
                  "Keep task.evidence verbatim in the current user's original language. "
                  "Write clarification questions in the user's language. "
                  "The query language does not change the final answer language."
                  "\nFor a broad POLICY_DETAILS request asking what insurance, purchased coverages "
                  "or selected options the user has, set policy_overview_language to 'en' for an English "
                  "reply or 'cs' for a Czech reply. This requests a summary of recorded selections only. "
                  "For specific limits, dates, premiums, people, procedures, claim eligibility, unclear "
                  "follow-ups or other reply languages, leave policy_overview_language null. "
                  "Never set it on COVERAGE_CHECK, PROCEDURE or GENERAL_QUESTION tasks."
            ),
            user_message=message,
            context=planning_context,
            response_model=QueryPlan,
        )

        if plan.action == QueryPlanAction.EXECUTE:

            for task in plan.tasks:
                evidence = task.evidence.strip()

                if evidence.casefold() not in message.casefold():
                    task.evidence = message.strip()[:500]

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
