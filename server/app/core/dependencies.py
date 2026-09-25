from functools import lru_cache

from app.core.config import settings
from app.llm.providers.groq_provider import GroqProvider
from app.services.chat_service import ChatService
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService


@lru_cache
def get_llm_service() -> LLMService:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    if not settings.groq_model:
        raise RuntimeError("GROQ_MODEL is not configured")

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


def get_chat_service() -> ChatService:
    return ChatService(
        retrieval_service=get_retrieval_service(),
        llm_service=get_llm_service(),
    )