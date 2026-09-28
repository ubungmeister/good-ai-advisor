from typing import TypeVar

from pydantic import BaseModel

from app.llm.base import BaseLLMProvider


T = TypeVar(
    "T",
    bound=BaseModel,
)


class LLMService:

    def __init__(
        self,
        provider: BaseLLMProvider,
    ):
        self.provider = provider

    async def generate_answer(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str | None = None,
    ) -> str:
        return await self.provider.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            context=context,
        )

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_message: str,
        response_model: type[T],
        context: str | None = None,
    ) -> T:
        return await self.provider.generate_structured(
            system_prompt=system_prompt,
            user_message=user_message,
            response_model=response_model,
            context=context,
        )