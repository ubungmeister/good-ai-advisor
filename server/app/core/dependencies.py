from functools import lru_cache

from app.core.config import settings
from app.llm.providers.groq_provider import GroqProvider
from app.services.chat_service import ChatService
from app.services.critical_flow_service import CriticalFlowService
from app.services.deterministic_guard_service import DeterministicGuardService
from app.services.grounding_fact_builder import GroundingFactBuilder
from app.services.grounding_validator import GroundingValidator
from app.services.llm_service import LLMService
from app.services.message_source_service import MessageSourceService
from app.services.policy_service import PolicyService
from app.services.response_validator import ResponseValidator
from app.services.retrieval_service import RetrievalService
from app.services.safe_response_service import SafeResponseService
from app.services.safety_classifier import SafetyClassifier
from app.services.safety_router import SafetyRouter
from app.services.query_planner import QueryPlanner
from app.services.task_prioritizer import TaskPrioritizer
from app.services.task_router import TaskRouter
from app.services.context_builder import ContextBuilder
from app.services.validation_decision_policy import ValidationDecisionPolicy
from app.services.conversation_service import ConversationService


@lru_cache
def get_llm_service() -> LLMService:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    if not settings.groq_model:
        raise RuntimeError("GROQ_MODEL is not configured.")

    provider = GroqProvider(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
    )

    return LLMService(
        provider=provider,
    )


@lru_cache
def get_retrieval_service() -> RetrievalService:
    return RetrievalService()


@lru_cache
def get_safety_classifier() -> SafetyClassifier:
    return SafetyClassifier(
        llm_service=get_llm_service(),
    )


@lru_cache
def get_safety_router() -> SafetyRouter:
    return SafetyRouter()

@lru_cache
def get_critical_flow_service() -> CriticalFlowService:
    return CriticalFlowService()

@lru_cache
def get_deterministic_guard_service() -> DeterministicGuardService:
    return DeterministicGuardService()


@lru_cache
def get_grounding_fact_builder() -> GroundingFactBuilder:
    return GroundingFactBuilder()


@lru_cache
def get_grounding_validator() -> GroundingValidator:
    return GroundingValidator(
        llm_service=get_llm_service(),
    )


@lru_cache
def get_validation_decision_policy() -> ValidationDecisionPolicy:
    return ValidationDecisionPolicy()


@lru_cache
def get_response_validator() -> ResponseValidator:
    return ResponseValidator(
        guard_service=get_deterministic_guard_service(),
        grounding_fact_builder=get_grounding_fact_builder(),
        grounding_validator=get_grounding_validator(),
        decision_policy=get_validation_decision_policy(),
    )

def get_chat_service() -> ChatService:
    return ChatService(
        retrieval_service=get_retrieval_service(),
        llm_service=get_llm_service(),

        safety_classifier=get_safety_classifier(),
        safety_router=get_safety_router(),
        critical_flow_service=get_critical_flow_service(),

        query_planner=get_query_planner(),
        task_prioritizer=get_task_prioritizer(),
        task_router=get_task_router(),

        policy_service=get_policy_service(),
        context_builder=get_context_builder(),

        response_validator=get_response_validator(),
        safe_response_service=get_safe_response_service(),
        conversation_service=get_conversation_service(),
        message_source_service=get_message_source_service(),
    )

@lru_cache
def get_query_planner() -> QueryPlanner:
    return QueryPlanner(
        llm_service=get_llm_service(),
    )


@lru_cache
def get_task_prioritizer() -> TaskPrioritizer:
    return TaskPrioritizer()


@lru_cache
def get_task_router() -> TaskRouter:
    return TaskRouter()


@lru_cache
def get_policy_service() -> PolicyService:
    return PolicyService()


@lru_cache
def get_context_builder() -> ContextBuilder:
    return ContextBuilder()

@lru_cache
def get_safe_response_service() -> SafeResponseService:
    return SafeResponseService()

@lru_cache
def get_conversation_service() -> ConversationService:
    return ConversationService()

@lru_cache
def get_message_source_service() -> MessageSourceService:
    return MessageSourceService()