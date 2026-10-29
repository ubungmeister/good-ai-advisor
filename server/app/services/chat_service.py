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
from app.services.chat_context import (
    DEFAULT_CONVERSATION_CONTEXT_MESSAGE_LIMIT,
    format_conversation_history, format_conversation_context,
)
from app.services.conversation_resolver import (
    ConversationResolver,
    ConversationResolutionAction,
)
from app.services.conversation_resolver import ConversationResolver
from app.services.conversation_resolver import ConversationResolver
from app.prompts.answer_generation import (
    INSURANCE_ANSWER_SYSTEM_PROMPT,
)

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
            ai_run_service: AiRunService,
            conversation_resolver: ConversationResolver,

    ):
        self.conversation_resolver = conversation_resolver
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
    ) -> tuple[str, uuid.UUID]:

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

        # 1. Load recent messages from previous turns.
        previous_messages = self.conversation_service.get_recent_messages(
            db=db,
            conversation_id=conversation.id,
            user_id=user_id,
            limit=DEFAULT_CONVERSATION_CONTEXT_MESSAGE_LIMIT,
        )

        conversation_history = format_conversation_history(
            messages=previous_messages,
        )

        conversation_context = format_conversation_context(
            messages=previous_messages,
        )



        # Save the current user message after loading history.
        self.conversation_service.add_message(
            db=db,
            conversation_id=conversation.id,
            role=ConversationRole.USER,
            content=message,
        )

        # resolution = await self.conversation_resolver.resolve(
        #     message=message,
        #     conversation_context=conversation_context,
        # )


        # 2. Save the current user message only after loading history.
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

            answer = self._save_assistant_answer(
                db=db,
                conversation_id=conversation.id,
                answer=answer,
                latency_ms=latency_ms,
                safety_result=safety_decision.category.value,
            )

            return answer, conversation.id

        # =====================================================
        # 3. QUERY PLANNER
        # =====================================================
        # 3. Resolve the current message against previous conversation turns.
        resolution = await self.conversation_resolver.resolve(
            message=message,
            conversation_context=conversation_context,
        )

        if resolution.action == ConversationResolutionAction.NEEDS_CLARIFICATION:
            latency_ms = int(
                (time.perf_counter() - total_start) * 1000
            )

            answer = self._save_assistant_answer(
                db=db,
                conversation_id=conversation.id,
                answer=resolution.clarification_question,
                latency_ms=latency_ms,
                safety_result=safety_decision.category.value,
            )

            return answer, conversation.id

        resolved_request = (
            resolution.resolved_request
            if resolution.action == ConversationResolutionAction.RESOLVED_FOLLOW_UP
            else None
        )

        plan = await self.query_planner.plan(
            message=message,
            conversation_history=conversation_history,
            resolved_request=resolved_request,
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

            latency_ms = int(
                (time.perf_counter() - total_start) * 1000
            )

            answer = self._save_assistant_answer(
                db=db,
                conversation_id=conversation.id,
                answer=answer,
                latency_ms=latency_ms,
                safety_result=safety_decision.category.value,
            )
            return answer, conversation.id

        # =====================================================
        # 7. FINAL LLM
        # =====================================================

        print("\n8. FINAL LLM START")

        answer = await self._generate_validated_answer(
            message=message,
            context=context,
            task_results=task_results,
            system_prompt=INSURANCE_ANSWER_SYSTEM_PROMPT,
            conversation_history=conversation_history,

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

        task_results = task_results

        answer = self._save_assistant_answer(
            db=db,
            conversation_id=conversation.id,
            answer=answer,
            latency_ms=int(total_time * 1000),
            safety_result=safety_decision.category.value,
            task_results=task_results,
        )
        return answer, conversation.id

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
            conversation_history: str,
            system_prompt: str,
    ) -> str:

        answer_context = build_answer_context(
            trusted_context=context,
            conversation_history=conversation_history,
        )

        draft_answer = await self.llm_service.generate_answer(
            system_prompt=INSURANCE_ANSWER_SYSTEM_PROMPT,
            user_message=message,
            context=answer_context
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

            regeneration_context = build_regeneration_context(
                trusted_context=context,
                conversation_history=conversation_history,
                previous_answer=draft_answer,
                validation=validation,
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
    def _validation_fallback() -> str:
        return (
            "I could not verify a sufficiently grounded "
            "answer from the available trusted insurance "
            "information. Please check the policy "
            "documentation or contact support."
        )

