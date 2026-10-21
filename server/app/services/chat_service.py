import time
import uuid
import json

from app.models import ConversationRole
from app.schemas.query_plan import TaskType
from app.services.conversation_service import ConversationService
from app.services.message_source_service import MessageSourceService
from sqlalchemy.orm import Session

from app.schemas.policy import PolicyDetailsResponse
from app.schemas.safety import SafetyRoute
from app.schemas.task_result import TaskResult, RetrievalTaskContent, RetrievedChunk, PolicyTaskContent
from app.schemas.task_routing import TaskTarget
from app.schemas.response_validation import ValidationAction
from app.services.response_validator import ResponseValidator
from app.services.safe_response_service import SafeResponseService
from app.services.ai_run_service import AiRunService

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
            response_validator: ResponseValidator,
            safe_response_service: SafeResponseService,
            conversation_service: ConversationService,
            message_source_service: MessageSourceService,
            ai_run_service: AiRunService
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

        self.response_validator = response_validator
        self.safe_response_service = safe_response_service
        self.conversation_service = conversation_service
        self.message_source_service = message_source_service
        self.ai_run_service = ai_run_service

    async def generate_answer(
        self,
        *,
        db: Session,
        message: str,
        user_id: uuid.UUID | None = None,
        policy_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> str:

        total_start = time.perf_counter()

        if user_id is None:
            raise ValueError(
                "Chat persistence requires user_id."
            )

        conversation = self.conversation_service.get_or_create(
            db=db,
            user_id=user_id,
            policy_id=policy_id,
            conversation_id=conversation_id,
        )

        self.conversation_service.add_message(
            db=db,
            conversation_id=conversation.id,
            role=ConversationRole.USER,
            content=message,
        )

        active_policy_id = conversation.policy_id

        print("\n========================================")
        print("CHAT FLOW START")
        print("MESSAGE:", message)
        print("USER ID:", user_id)
        print("POLICY ID:", active_policy_id)
        print("========================================")
        # =====================================================
        # 1. SAFETY
        # =====================================================

        safety_decision = (
            await self.safety_classifier.classify(
                message=message,
            )
        )
        print("\n1. SAFETY DONE")
        print("SAFETY DECISION:", safety_decision)

        safety_route = self.safety_router.route(
            decision=safety_decision,
        )
        print("2. SAFETY ROUTE:", safety_route)

        # =====================================================
        # 2. CRITICAL FLOW
        # =====================================================

        if (
                safety_route
                == SafetyRoute.CRITICAL_FLOW
        ):
            answer = self.critical_flow_service.handle(
                decision=safety_decision,
            )

            return self._save_assistant_answer(
                db=db,
                conversation_id=conversation.id,
                answer=answer,
            )

        # =====================================================
        # 3. QUERY PLANNER
        # =====================================================

        plan = await self.query_planner.plan(
            message=message,
        )

        print("\n3. QUERY PLANNER DONE")
        print("PLAN:", plan)

        # =====================================================
        # 4. PRIORITIZE TASKS
        # =====================================================

        tasks = (
            self.task_prioritizer.prioritize(
                plan=plan,
            )
        )
        print("\n4. TASK PRIORITIZER DONE")
        print("PRIORITIZED TASKS:", tasks)

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
            print("\n5. TASK ROUTED")
            print("TASK TYPE:", task.type)
            print("TASK QUERY:", task.query)
            print("TARGETS:", routed_task.targets)

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

                    retrieval_content = RetrievalTaskContent(
                        chunks=[
                            RetrievedChunk(
                                id=chunk.id,
                                document_id=chunk.document_id,
                                content=chunk.content,
                                score=score,
                                page_number=chunk.page_number,
                                article_number=chunk.article_number,
                                section_title=chunk.section_title,
                                coverage_code=chunk.coverage_code,
                            )
                            for chunk, score in retrieval_results
                        ]
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
                        or active_policy_id is None
                    ):
                        raise ValueError(
                            "Policy task requires "
                            "user_id and policy_id."
                        )

                    policy_details = (
                        self.policy_service
                        .get_policy_details_for_user(
                            db=db,
                            policy_id=active_policy_id,
                            user_id=user_id,
                        )
                    )

                    if policy_details is None:
                        raise ValueError(
                            "Policy was not found "
                            "or does not belong "
                            "to the user."
                        )

                    policy_content = (
                        PolicyTaskContent.model_validate(
                            policy_details
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
        print("\n6. TASK EXECUTION DONE")

        print(
            "TASK RESULTS:",
            [
                (
                    result.task_type.value,
                    result.target.value,
                )
                for result in task_results
            ],
        )
        context = self.context_builder.build(
            results=task_results,
        )

        print("\n7. CONTEXT BUILDER DONE")
        print("CONTEXT LENGTH:", len(context))

        print(
            "CONTEXT PREVIEW:\n",
            context[:1500],
        )

        if not context:
            answer = (
                "I do not have enough trusted "
                "information to answer this question."
            )

            return self._save_assistant_answer(
                db=db,
                conversation_id=conversation.id,
                answer=answer,
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
        print("\n8. FINAL LLM START")

        answer = await self._generate_validated_answer(
            message=message,
            context=context,
            task_results=task_results,
            system_prompt=system_prompt,
        )

        print("9. FINAL LLM + VALIDATION DONE")
        print("ANSWER:", answer)

        total_time = (
                time.perf_counter()
                - total_start
        )

        print("\n========================================")
        print("CHAT FLOW COMPLETE")
        print(
            f"TOTAL CHAT TIME: "
            f"{total_time:.3f} sec"
        )
        print("========================================\n")

        return self._save_assistant_answer(
            db=db,
            conversation_id=conversation.id,
            answer=answer,
        )

    def _save_assistant_answer(
            self,
            *,
            db: Session,
            conversation_id: uuid.UUID,
            answer: str,
            latency_ms: int,
            safety_result: str,
            task_results: list[TaskResult] | None = None,
    ) -> str:

        assistant_message = (
            self.conversation_service.add_message(
                db=db,
                conversation_id=conversation_id,
                role=ConversationRole.ASSISTANT,
                content=answer,
            )
        )

        if task_results:
            self.message_source_service.save_from_task_results(
                db=db,
                message_id=assistant_message.id,
                task_results=task_results,
            )

        self.ai_run_service.save_run(
            db=db,
            conversation_id=conversation_id,
            message_id=assistant_message.id,
            latency_ms=latency_ms,
            safety_result=safety_result,
            task_results=task_results,
        )

        return answer

    async def _generate_validated_answer(
            self,
            *,
            message: str,
            context: str,
            task_results: list[TaskResult],
            system_prompt: str,
    ) -> str:

        draft_answer = await self.llm_service.generate_answer(
            system_prompt=system_prompt,
            user_message=message,
            context=context,
        )

        print("\nVALIDATION: FIRST DRAFT")
        print("DRAFT:", draft_answer)

        validation = await self.response_validator.validate(
            question=message,
            draft_answer=draft_answer,
            task_results=task_results,
            regeneration_count=0,
        )

        print("VALIDATION RESULT:", validation)

        if validation.action == ValidationAction.OK:
            return draft_answer

        if validation.action in {
            ValidationAction.HANDOFF,
            ValidationAction.REJECT,
        }:
            return self.safe_response_service.build(
                action=validation.action,
            )

        if validation.action == ValidationAction.REGENERATE:

            regeneration_context = (
                self._build_regeneration_context(
                    trusted_context=context,
                    previous_answer=draft_answer,
                    validation=validation,
                )
            )

            print("\nREGENERATION START")

            regenerated_answer = (
                await self.llm_service.generate_answer(
                    system_prompt=system_prompt,
                    user_message=message,
                    context=regeneration_context,
                )
            )

            print(
                "REGENERATED ANSWER:",
                regenerated_answer,
            )

            second_validation = (
                await self.response_validator.validate(
                    question=message,
                    draft_answer=regenerated_answer,
                    task_results=task_results,
                    regeneration_count=1,
                )
            )

            print(
                "SECOND VALIDATION RESULT:",
                second_validation,
            )

            if (
                    second_validation.action
                    == ValidationAction.OK
            ):
                return regenerated_answer

            return self.safe_response_service.build(
                action=second_validation.action,
            )

        return self.safe_response_service.build(
            action=ValidationAction.HANDOFF,
        )

    @staticmethod
    def _build_regeneration_context(
            *,
            trusted_context: str,
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
    [TRUSTED CONTEXT]

    {trusted_context}

    [PREVIOUS DRAFT - NOT TRUSTED EVIDENCE]

    {previous_answer}

    [VALIDATION FEEDBACK]

    {feedback}

    Generate a corrected answer.

    Rules:
    - Use only the TRUSTED CONTEXT as factual evidence.
    - Correct the problems identified in VALIDATION FEEDBACK.
    - Do not treat the previous draft as evidence.
    - Do not invent missing insurance facts.
    - Keep the answer focused on the user's original question.
    """

    @staticmethod
    def _validation_fallback() -> str:
        return (
            "I could not verify a sufficiently grounded "
            "answer from the available trusted insurance "
            "information. Please check the policy "
            "documentation or contact support."
        )

