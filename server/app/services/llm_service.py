from app.llm.base import BaseLLMProvider


class LLMService:

    def __init__(self, provider: BaseLLMProvider):
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