import logging
import time
import asyncio
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
    format_conversation_history,
    build_answer_context,
    build_regeneration_context,
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
from app.services.query_planner import QueryPlanner, QueryPlanAction
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
from app.schemas.response_validation import ValidationResult
from app.services.task_router import TaskRouter
from app.services.document_context import section_label
from app.services.policy_overview import render_policy_overview


logger = logging.getLogger(__name__)


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
    ) -> tuple[str, uuid.UUID]:

        total_start = time.perf_counter()

        if user_id is None:
            raise ValueError(
                "Chat persistence requires user_id."
            )

        print("[CHAT] START - preparing conversation", flush=True)
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



        # 2. Save the current user message only after loading history.
        self.conversation_service.add_message(
            db=db,
            conversation_id=conversation.id,
            role=ConversationRole.USER,
            content=message,
        )

        active_policy_id = conversation.policy_id
        print("[CHAT] Conversation ready", flush=True)

        # =====================================================
        # 1. SAFETY
        # =====================================================

        started = time.perf_counter()

        try:
            safety_decision, safety_route, planning_task = await self._prepare_turn(
                message=message, conversation_history=conversation_history,
            )
        finally:
            print(f"[CHAT] Safety elapsed: {time.perf_counter() - started:.2f}s", flush=True)

        # =====================================================
        # 2. CRITICAL FLOW
        # =====================================================

        if (
                safety_route
                == SafetyRoute.CRITICAL_FLOW
        ):
            print("[CHAT] Critical response selected", flush=True)
            answer = self.critical_flow_service.handle(
                decision=safety_decision,
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
        # QUERY PLANNER
        # =====================================================

        plan = await planning_task
        print(f"[CHAT] Plan ready: action={plan.action.value}, tasks={len(plan.tasks)}", flush=True)


        # A clarification is a complete response for this turn.
        # Do not prioritize or execute tasks.
        if plan.action == QueryPlanAction.NEEDS_CLARIFICATION:
            print("[CHAT] Clarification selected", flush=True)
            clarification_question = plan.clarification_question

            # The QueryPlan schema guarantees this is present for
            # NEEDS_CLARIFICATION. Keep the runtime guard as a safeguard.
            if clarification_question is None:
                raise RuntimeError(
                    "Clarification plan has no clarification question."
                )

            latency_ms = int(
                (time.perf_counter() - total_start) * 1000
            )

            answer = self._save_assistant_answer(
                db=db,
                conversation_id=conversation.id,
                answer=clarification_question,
                latency_ms=latency_ms,
                safety_result=safety_decision.category.value,
            )

            return answer, conversation.id


        # =====================================================
        # 4. PRIORITIZE TASKS
        # =====================================================

        tasks = (
            self.task_prioritizer.prioritize(
                plan=plan,
            )
        )
        print(f"[CHAT] Tasks prioritized: {len(tasks)}", flush=True)

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
                task_started = time.perf_counter()
                print(f"[CHAT] Task started: {task.type.value} -> {target.value}", flush=True)

                # =============================================
                # RETRIEVAL
                # =============================================

                if (
                    target
                    == TaskTarget.RETRIEVAL
                ):
                    # Never search across all product versions.
                    # Resolve the scope from an owned policy, not LLM output.
                    if active_policy_id is None:
                        return self._policy_unavailable(
                            db=db, conversation_id=conversation.id, started=total_start,
                            safety_result=safety_decision.category.value,
                        )

                    authorized_policy = self.policy_service.get_policy_for_user(
                        db=db,
                        policy_id=active_policy_id,
                        user_id=user_id,
                    )
                    if authorized_policy is None:
                        return self._policy_unavailable(
                            db=db, conversation_id=conversation.id, started=total_start,
                            safety_result=safety_decision.category.value,
                        )

                    retrieval_results = (
                        self.retrieval_service.search(
                            db=db,
                            question=task.query,
                            limit=5,
                            product_version_id=authorized_policy.product_version_id,
                        )
                    )

                    print(f"[CHAT] Retrieval returned {len(retrieval_results)} chunks", flush=True)
                    if not retrieval_results:
                        print(f"[CHAT] Task elapsed: {time.perf_counter() - task_started:.2f}s", flush=True)
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
                                section_title=section_label(chunk),
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
                        return self._policy_unavailable(
                            db=db, conversation_id=conversation.id, started=total_start,
                            safety_result=safety_decision.category.value,
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
                        return self._policy_unavailable(
                            db=db, conversation_id=conversation.id, started=total_start,
                            safety_result=safety_decision.category.value,
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

                print(f"[CHAT] Task completed in {time.perf_counter() - task_started:.2f}s", flush=True)

        # =====================================================
        # 6. CONTEXT BUILDER
        # =====================================================
        if (len(tasks) == 1 and tasks[0].policy_overview_language is not None
                and tasks[0].type == TaskType.POLICY_DETAILS and len(task_results) == 1
                and task_results[0].target == TaskTarget.POLICY
                and isinstance(task_results[0].content, PolicyTaskContent)):
            print("[CHAT] Rendering recorded-policy overview", flush=True)
            # No generated prose: every listed value comes directly from the
            # ownership-checked, schema-validated policy result above.
            answer = render_policy_overview(task_results[0].content, tasks[0].policy_overview_language)
            answer = self._save_assistant_answer(
                db=db, conversation_id=conversation.id, answer=answer,
                latency_ms=int((time.perf_counter() - total_start) * 1000),
                safety_result=safety_decision.category.value, task_results=task_results,
                answer_source="policy-overview-v1",
            )
            return answer, conversation.id

        context = self.context_builder.build(
            results=task_results,
        )
        print(f"[CHAT] Context built: {len(task_results)} results, {len(context)} characters", flush=True)


        if not context:
            print("[CHAT] Fallback selected: no trusted context", flush=True)
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


        answer = await self._generate_validated_answer(
            message=message,
            context=context,
            task_results=task_results,
            system_prompt=INSURANCE_ANSWER_SYSTEM_PROMPT,
            conversation_history=conversation_history,

        )


        total_time = (
                time.perf_counter()
                - total_start
        )

        logger.info("TOTAL CHAT TIME: %.3f sec", total_time)

        task_results = task_results

        save_started = time.perf_counter()

        answer = self._save_assistant_answer(
            db=db,
            conversation_id=conversation.id,
            answer=answer,
            latency_ms=int(total_time * 1000),
            safety_result=safety_decision.category.value,
            task_results=task_results,
        )

        logger.info("DB SAVE TOTAL: %.3fs", time.perf_counter() - save_started)
        logger.info("CHAT INCLUDING SAVE: %.3fs", time.perf_counter() - total_start)

        return answer, conversation.id
        # answer = self._save_assistant_answer(
        #     db=db,
        #     conversation_id=conversation.id,
        #     answer=answer,
        #     latency_ms=int(total_time * 1000),
        #     safety_result=safety_decision.category.value,
        #     task_results=task_results,
        # )
        # return answer, conversation.id

    async def _prepare_turn(self, *, message, conversation_history):
        # Planning is read-only. No plan is executed until the safety route is
        # known; critical flows discard it and cancellation cleans up the task.
        async def plan():
            started = time.perf_counter()
            try:
                return await self.query_planner.plan(message=message, conversation_history=conversation_history)
            finally:
                print(f"[CHAT] Planning elapsed: {time.perf_counter() - started:.2f}s", flush=True)

        print("[CHAT] Safety and planning started concurrently", flush=True)
        planning_task = asyncio.create_task(plan())
        try:
            decision = await self.safety_classifier.classify(message=message)
            route = self.safety_router.route(decision=decision)
            if route == SafetyRoute.CRITICAL_FLOW:
                print("[CHAT] Normal planning discarded", flush=True)
                planning_task.cancel()
                await asyncio.gather(planning_task, return_exceptions=True)
                return decision, route, None
            return decision, route, planning_task
        except BaseException:
            planning_task.cancel()
            await asyncio.gather(planning_task, return_exceptions=True)
            raise

    def _policy_unavailable(self, *, db, conversation_id, started, safety_result):
        print("[CHAT] Fallback selected: policy unavailable", flush=True)
        answer = self._save_assistant_answer(
            db=db, conversation_id=conversation_id,
            answer=SafeResponseService.POLICY_UNAVAILABLE_MESSAGE,
            latency_ms=int((time.perf_counter() - started) * 1000),
            safety_result=safety_result,
        )
        return answer, conversation_id

    def _save_assistant_answer(
            self,
            *,
            db: Session,
            conversation_id: uuid.UUID,
            answer: str,
            latency_ms: int,
            safety_result: str,
            task_results: list[TaskResult] | None = None,
            answer_source: str | None = None,
    ) -> str:

        save_started = time.perf_counter()
        print("[CHAT] Saving response", flush=True)
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
            **({"answer_source": answer_source} if answer_source is not None else {}),
        )

        save_elapsed = time.perf_counter() - save_started
        print(f"[CHAT] Saved in {save_elapsed:.2f}s; COMPLETE in {latency_ms / 1000 + save_elapsed:.2f}s", flush=True)
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

        print("[CHAT] Answer generation started", flush=True)
        draft_answer = await self.llm_service.generate_answer(
            system_prompt=INSURANCE_ANSWER_SYSTEM_PROMPT,
            user_message=message,
            context=answer_context
        )

        print("[CHAT] Draft ready; grounding validation started", flush=True)
        validation = await self.response_validator.validate(
            question=message,
            draft_answer=draft_answer,
            task_results=task_results,
            regeneration_count=0,
        )
        codes = ",".join(issue.code.value for issue in validation.issues) or "none"
        print(f"[CHAT] Validation: {validation.action.value}; grounding={validation.grounding.value}; issues={codes}", flush=True)

        if validation.action == ValidationAction.OK:
            return draft_answer

        if validation.action in {
            ValidationAction.HANDOFF,
            ValidationAction.REJECT,
        }:
            print("[CHAT] Validation fallback selected", flush=True)
            return self.safe_response_service.build(
                action=validation.action,
            )

        if validation.action == ValidationAction.REGENERATE:
            print("[CHAT] Regeneration started", flush=True)

            regeneration_context = build_regeneration_context(
                trusted_context=context,
                conversation_history=conversation_history,
                previous_answer=draft_answer,
                validation=validation,
            )


            regenerated_answer = (
                await self.llm_service.generate_answer(
                    system_prompt=system_prompt,
                    user_message=message,
                    context=regeneration_context,
                )
            )


            second_validation = (
                await self.response_validator.validate(
                    question=message,
                    draft_answer=regenerated_answer,
                    task_results=task_results,
                    regeneration_count=1,
                )
            )
            codes = ",".join(issue.code.value for issue in second_validation.issues) or "none"
            print(f"[CHAT] Revalidation: {second_validation.action.value}; grounding={second_validation.grounding.value}; issues={codes}", flush=True)

            if (
                    second_validation.action
                    == ValidationAction.OK
            ):
                return regenerated_answer

            print("[CHAT] Revalidation fallback selected", flush=True)
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

