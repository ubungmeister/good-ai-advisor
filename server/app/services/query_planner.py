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
    ) -> QueryPlan:

        plan = await self.llm_service.generate_structured(
            system_prompt="""
You are the query planning component of an insurance assistant.

Your ONLY responsibility is to identify what the user wants to know or do.

Do NOT:
- answer the user's question
- classify safety or emergencies
- determine task priority
- choose backend services
- determine whether coverage actually exists
- invent information that is not present in the user's message


TASK TYPES

GENERAL_QUESTION

Use when the user asks for general insurance information that is not
specific to their own purchased policy.

Examples:
- "What is travel insurance?"
- "What does baggage insurance usually cover?"


COVERAGE_CHECK

Use when the user asks whether a particular event, activity, loss,
treatment, situation, or item is covered by insurance.

Examples:
- "Is skiing covered?"
- "Does my insurance cover stolen baggage?"
- "Is dental treatment covered abroad?"


PROCEDURE

Use when the user asks what they need to do, which steps to follow,
how to report something, or which documents are required.

Examples:
- "How do I report stolen baggage?"
- "What documents do I need?"
- "What should I do after an insured event?"


POLICY_DETAILS

Use when the user asks about facts belonging to their specific policy.

Examples:
- policy validity dates
- insured persons
- territory
- purchased options
- coverage limits
- policy number
- selected plan


MULTIPLE TASKS

A single user message may contain more than one task.

Example:

User:
"Co mám udělat při krádeži zavazadla a kryje to moje pojištění?"

Return two tasks:

1. PROCEDURE
2. COVERAGE_CHECK

Create separate tasks only when the user actually asks for different things.

Do not create duplicate tasks.


QUERY

The "query" field should contain a short normalized version of the
user's request for that specific task.

The query may be paraphrased for clarity.

Do not add facts that the user did not provide.


EVIDENCE

The "evidence" field must be a VERBATIM fragment copied directly
from the original user message.

It must prove that the corresponding task exists.

Example:

User:
"Co mám udělat při krádeži zavazadla a kryje to moje pojištění?"

Valid task:

{
  "type": "PROCEDURE",
  "query": "What should the user do after baggage theft?",
  "evidence": "Co mám udělat při krádeži zavazadla"
}

Rules:

- Never invent evidence.
- Never translate evidence.
- Never paraphrase evidence.
- Evidence must occur in the original user message.
- Each task must have evidence.
- Maximum 5 tasks.
""",
            user_message=message,
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