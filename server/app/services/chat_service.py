import time
import uuid

from sqlalchemy.orm import Session

from app.schemas.policy import PolicyDetailsResponse
from app.schemas.safety import SafetyRoute
from app.schemas.task_result import TaskResult
from app.schemas.task_routing import TaskTarget

from app.services.context_builder import ContextBuilder
from app.services.critical_flow_service import (
    CriticalFlowService,
)
from app.services.llm_service import LLMService
from app.services.policy_service import PolicyService
from app.services.query_planner import QueryPlanner
from app.services.retrieval_service import (
    RetrievalService,
)
from app.services.safety_classifier import (
    SafetyClassifier,
)
from app.services.safety_router import SafetyRouter
from app.services.task_prioritizer import (
    TaskPrioritizer,
)
from app.services.task_router import TaskRouter


class ChatService:

    def __init__(
        self,
        *,
        retrieval_service: RetrievalService,
        llm_service: LLMService,
        safety_classifier: SafetyClassifier,
        safety_router: SafetyRouter,
        critical_flow_service: CriticalFlowService,
        query_planner: QueryPlanner,
        task_prioritizer: TaskPrioritizer,
        task_router: TaskRouter,
        policy_service: PolicyService,
        context_builder: ContextBuilder,
    ):
        self.retrieval_service = retrieval_service
        self.llm_service = llm_service

        self.safety_classifier = safety_classifier
        self.safety_router = safety_router
        self.critical_flow_service = (
            critical_flow_service
        )

        self.query_planner = query_planner
        self.task_prioritizer = task_prioritizer
        self.task_router = task_router

        self.policy_service = policy_service
        self.context_builder = context_builder

    async def generate_answer(
        self,
        *,
        db: Session,
        message: str,
        user_id: uuid.UUID | None = None,
        policy_id: uuid.UUID | None = None,
    ) -> str:

        total_start = time.perf_counter()

        # =====================================================
        # 1. SAFETY
        # =====================================================

        safety_decision = (
            await self.safety_classifier.classify(
                message=message,
            )
        )

        safety_route = self.safety_router.route(
            decision=safety_decision,
        )

        # =====================================================
        # 2. CRITICAL FLOW
        # =====================================================

        if (
            safety_route
            == SafetyRoute.CRITICAL_FLOW
        ):
            return (
                self.critical_flow_service.handle(
                    decision=safety_decision,
                )
            )

        # =====================================================
        # 3. QUERY PLANNER
        # =====================================================

        plan = await self.query_planner.plan(
            message=message,
        )

        # =====================================================
        # 4. PRIORITIZE TASKS
        # =====================================================

        tasks = (
            self.task_prioritizer.prioritize(
                plan=plan,
            )
        )

        # =====================================================
        # 5. EXECUTE ROUTED TASKS
        # =====================================================

        task_results: list[TaskResult] = []

        for task in tasks:

            routed_task = (
                self.task_router.route(
                    task=task,
                )
            )

            for target in routed_task.targets:

                # =============================================
                # RETRIEVAL
                # =============================================

                if (
                    target
                    == TaskTarget.RETRIEVAL
                ):

                    retrieval_results = (
                        self.retrieval_service.search(
                            db=db,
                            question=task.query,
                            limit=5,
                        )
                    )

                    if not retrieval_results:
                        continue

                    retrieval_content = (
                        "\n\n".join(
                            (
                                f"[DOCUMENT {index}]\n"
                                f"{chunk.content}"
                            )
                            for index, (
                                chunk,
                                _score,
                            ) in enumerate(
                                retrieval_results,
                                start=1,
                            )
                        )
                    )

                    task_results.append(
                        TaskResult(
                            task_type=task.type,
                            target=target,
                            content=(
                                retrieval_content
                            ),
                        )
                    )

                # =============================================
                # POLICY
                # =============================================

                elif (
                    target
                    == TaskTarget.POLICY
                ):

                    if (
                        user_id is None
                        or policy_id is None
                    ):
                        raise ValueError(
                            "Policy task requires "
                            "user_id and policy_id."
                        )

                    policy_details = (
                        self.policy_service
                        .get_policy_details_for_user(
                            db=db,
                            policy_id=policy_id,
                            user_id=user_id,
                        )
                    )

                    if policy_details is None:
                        raise ValueError(
                            "Policy was not found "
                            "or does not belong "
                            "to the user."
                        )

                    # Convert ORM objects returned by
                    # PolicyService into our clean API DTO.
                    policy_dto = (
                        PolicyDetailsResponse
                        .model_validate(
                            policy_details
                        )
                    )

                    policy_content = (
                        policy_dto.model_dump_json(
                            indent=2,
                        )
                    )

                    task_results.append(
                        TaskResult(
                            task_type=task.type,
                            target=target,
                            content=policy_content,
                        )
                    )

                # =============================================
                # UNKNOWN TARGET
                # =============================================

                else:
                    raise ValueError(
                        "Unsupported task target: "
                        f"{target}"
                    )

        # =====================================================
        # 6. CONTEXT BUILDER
        # =====================================================

        context = self.context_builder.build(
            results=task_results,
        )

        if not context:
            return (
                "I do not have enough trusted "
                "information to answer this question."
            )

        # =====================================================
        # 7. FINAL LLM
        # =====================================================

        system_prompt = """
You are an insurance assistant.

Answer the user's question using only the trusted
context provided to you.

The context may contain two kinds of information:

[POLICY FACTS]
Facts about the customer's actual purchased insurance,
including dates, coverages, options, insured people,
roles and travel details.

[INSURANCE DOCUMENTATION]
Relevant excerpts from official insurance terms
and documentation.

Rules:

- Use only information present in the provided context.
- Do not invent coverage, exclusions, limits, procedures,
  people, contract facts or insurance conditions.
- POLICY FACTS describe the customer's actual contract.
- INSURANCE DOCUMENTATION describes applicable insurance
  rules and conditions.
- For personalized coverage questions, combine contract
  facts and insurance documentation when both are present.
- Distinguish between a person being insured and a specific
  activity or event being covered.
- If the context is insufficient to answer confidently,
  clearly say that there is not enough information.
- Preserve the meaning of who must do what and to whom.
- Clearly distinguish mandatory requirements from optional
  information.
- Answer in the same language as the user.
"""

        answer = (
            await self.llm_service.generate_answer(
                system_prompt=system_prompt,
                user_message=message,
                context=context,
            )
        )

        total_time = (
            time.perf_counter()
            - total_start
        )

        print(
            f"TOTAL CHAT TIME: "
            f"{total_time:.3f} sec"
        )

        return answer