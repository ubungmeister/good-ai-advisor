from app.schemas.task_routing import TaskTarget
from app.services.context_builder import ContextBuilder
from app.services.policy_service import PolicyService
from app.services.query_planner import QueryPlanner
from app.services.task_prioritizer import TaskPrioritizer
from app.services.task_router import TaskRouter
from sqlalchemy.orm import Session
import uuid

from app.schemas.safety import SafetyRoute
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService
from app.services.safety_classifier import SafetyClassifier
from app.services.safety_router import SafetyRouter
from app.services.critical_flow_service import CriticalFlowService

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
        self.critical_flow_service = critical_flow_service

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

        # 1. Analyze safety before running the normal insurance flow.
        safety_decision = await self.safety_classifier.classify(
            message=message,
        )

        # 2. Deterministically decide which flow should handle the request.
        safety_route = self.safety_router.route(
            decision=safety_decision,
        )

        # 3. Critical requests must not continue through the normal RAG flow.
        if safety_route == SafetyRoute.CRITICAL_FLOW:
            return self.critical_flow_service.handle(
                decision=safety_decision,
            )

        # ---------------------------------------------
        # NORMAL FLOW
        # ---------------------------------------------

        # 1. Split the user's message into tasks.
        plan = await self.query_planner.plan(
            message=message,
        )

        # 2. Put tasks into deterministic order.
        tasks = self.task_prioritizer.prioritize(
            plan=plan,
        )

        # 3. Route every task to the required service(s).
        for task in tasks:

            routed_task = self.task_router.route(
                task=task,
            )

            for target in routed_task.targets:

                # -----------------------------------------
                # General insurance documentation / RAG
                # -----------------------------------------
                if target == TaskTarget.RETRIEVAL:

                    retrieval_results = (
                        self.retrieval_service.search(
                            db=db,
                            question=task.query,
                            limit=5,
                        )
                    )

                    print(
                        "RETRIEVAL RESULT:",
                        retrieval_results,
                    )

                # -----------------------------------------
                # Customer's actual insurance contract
                # -----------------------------------------
                elif target == TaskTarget.POLICY:

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
                            "or does not belong to the user."
                        )

                    print(
                        "POLICY RESULT:",
                        policy_details,
                    )

        context = "\n\n".join(
            f"[DOCUMENT {index}]\n{chunk.content}"
            for index, (chunk, _score) in enumerate(
                retrieval_results,
                start=1,
            )
        )

        system_prompt = """
You are an insurance assistant.

Answer the user's question strictly from the provided insurance documentation.

Rules:
- Read all provided document excerpts carefully.
- If any excerpt directly answers the question, use it.
- Do not ignore relevant information just because other excerpts are unrelated.
- Do not add examples, interpretations, terminology, procedures, limits,
  or assumptions that are not explicitly present in the provided documentation.
- Preserve the meaning of who must do what and to whom.
- Clearly distinguish mandatory requirements from optional information.
- If the documentation truly does not contain enough information, say so.
- Answer in the same language as the user.
"""

        return await self.llm_service.generate_answer(
            system_prompt=system_prompt,
            user_message=message,
            context=context,
        )

import time
import uuid

from sqlalchemy.orm import Session

from app.schemas.safety import SafetyRoute
from app.schemas.task_routing import TaskTarget

from app.services.context_builder import ContextBuilder
from app.services.critical_flow_service import CriticalFlowService
from app.services.llm_service import LLMService
from app.services.policy_service import PolicyService
from app.services.query_planner import QueryPlanner
from app.services.retrieval_service import RetrievalService
from app.services.safety_classifier import SafetyClassifier
from app.services.safety_router import SafetyRouter
from app.services.task_prioritizer import TaskPrioritizer
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
        self.critical_flow_service = critical_flow_service

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

        print("\n========================================")
        print("CHAT REQUEST START")
        print("MESSAGE:", message)
        print("USER ID:", user_id)
        print("POLICY ID:", policy_id)
        print("========================================")

        # =====================================================
        # 1. SAFETY
        # =====================================================

        print("\n1. SAFETY START")

        safety_start = time.perf_counter()

        safety_decision = await self.safety_classifier.classify(
            message=message,
        )

        safety_time = time.perf_counter() - safety_start

        print("2. SAFETY DONE")
        print("SAFETY DECISION:", safety_decision)
        print(f"SAFETY TIME: {safety_time:.3f} sec")

        # =====================================================
        # 2. SAFETY ROUTING
        # =====================================================

        safety_route = self.safety_router.route(
            decision=safety_decision,
        )

        print("3. SAFETY ROUTE:", safety_route)

        # =====================================================
        # 3. CRITICAL FLOW
        # =====================================================

        if safety_route == SafetyRoute.CRITICAL_FLOW:

            print("CRITICAL FLOW START")

            result = self.critical_flow_service.handle(
                decision=safety_decision,
            )

            total_time = (
                time.perf_counter()
                - total_start
            )

            print(
                f"TOTAL CHAT TIME: "
                f"{total_time:.3f} sec"
            )

            return result

        # =====================================================
        # 4. QUERY PLANNER
        # =====================================================

        print("\n4. QUERY PLANNER START")

        planner_start = time.perf_counter()

        plan = await self.query_planner.plan(
            message=message,
        )

        planner_time = (
            time.perf_counter()
            - planner_start
        )

        print("5. QUERY PLANNER DONE")
        print("PLAN:", plan)
        print(
            f"PLANNER TIME: "
            f"{planner_time:.3f} sec"
        )

        # =====================================================
        # 5. TASK PRIORITY
        # =====================================================

        print("\n6. TASK PRIORITIZER START")

        tasks = self.task_prioritizer.prioritize(
            plan=plan,
        )

        print("7. TASK PRIORITIZER DONE")
        print("TASKS:", tasks)

        # These are only for debug output.
        retrieval_count = 0
        policy_count = 0

        # =====================================================
        # 6. ROUTE + EXECUTE TASKS
        # =====================================================

        for task_index, task in enumerate(
            tasks,
            start=1,
        ):

            print("\n----------------------------------------")
            print(f"TASK #{task_index}")
            print("TYPE:", task.type)
            print("QUERY:", task.query)
            print("----------------------------------------")

            routed_task = self.task_router.route(
                task=task,
            )

            print(
                "8. ROUTED TARGETS:",
                routed_task.targets,
            )

            # -------------------------------------------------
            # Execute every target selected by TaskRouter.
            # -------------------------------------------------

            for target in routed_task.targets:

                # =============================================
                # RETRIEVAL TARGET
                # =============================================

                if target == TaskTarget.RETRIEVAL:

                    print("\n9. RETRIEVAL START")

                    retrieval_start = (
                        time.perf_counter()
                    )

                    retrieval_results = (
                        self.retrieval_service.search(
                            db=db,
                            question=task.query,
                            limit=5,
                        )
                    )

                    retrieval_time = (
                        time.perf_counter()
                        - retrieval_start
                    )

                    retrieval_count += 1

                    print("10. RETRIEVAL DONE")
                    print(
                        "RETRIEVAL RESULTS COUNT:",
                        len(retrieval_results),
                    )
                    print(
                        f"RETRIEVAL TIME: "
                        f"{retrieval_time:.3f} sec"
                    )

                    for index, (
                        chunk,
                        score,
                    ) in enumerate(
                        retrieval_results,
                        start=1,
                    ):
                        print(
                            f"  RESULT #{index}: "
                            f"score={score}"
                        )

                # =============================================
                # POLICY TARGET
                # =============================================

                elif target == TaskTarget.POLICY:

                    print("\n9. POLICY START")

                    if (
                        user_id is None
                        or policy_id is None
                    ):
                        raise ValueError(
                            "Policy task requires "
                            "user_id and policy_id."
                        )

                    policy_start = (
                        time.perf_counter()
                    )

                    policy_details = (
                        self.policy_service
                        .get_policy_details_for_user(
                            db=db,
                            policy_id=policy_id,
                            user_id=user_id,
                        )
                    )

                    policy_time = (
                        time.perf_counter()
                        - policy_start
                    )

                    if policy_details is None:
                        raise ValueError(
                            "Policy was not found "
                            "or does not belong "
                            "to the user."
                        )

                    policy_count += 1

                    print("10. POLICY DONE")
                    print(
                        "POLICY DETAILS:",
                        policy_details,
                    )
                    print(
                        f"POLICY TIME: "
                        f"{policy_time:.3f} sec"
                    )

                # =============================================
                # UNKNOWN TARGET
                # =============================================

                else:
                    raise ValueError(
                        f"Unsupported task target: "
                        f"{target}"
                    )

        # =====================================================
        # 7. TEMPORARY DEBUG RESPONSE
        # =====================================================
        #
        # IMPORTANT:
        #
        # We intentionally DO NOT run ContextBuilder or the
        # final LLM yet.
        #
        # Right now we only want to verify:
        #
        # Planner
        #   ↓
        # Prioritizer
        #   ↓
        # Router
        #   ↓
        # PolicyService / RetrievalService
        #
        # =====================================================

        total_time = (
            time.perf_counter()
            - total_start
        )

        print("\n========================================")
        print("ROUTING DEBUG COMPLETE")
        print(
            "RETRIEVAL CALLS:",
            retrieval_count,
        )
        print(
            "POLICY CALLS:",
            policy_count,
        )
        print(
            f"TOTAL CHAT TIME: "
            f"{total_time:.3f} sec"
        )
        print("========================================\n")

        return (
            "DEBUG routing completed successfully. "
            f"Retrieval calls: {retrieval_count}. "
            f"Policy calls: {policy_count}. "
            f"Total time: {total_time:.2f} sec."
        )