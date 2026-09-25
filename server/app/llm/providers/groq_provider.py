from groq import AsyncGroq
from groq.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from app.llm.base import BaseLLMProvider


class GroqProvider(BaseLLMProvider):

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
    ):
        self.client = AsyncGroq(api_key=api_key)
        self.model = model

    async def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str | None = None,
    ) -> str:

        user_content = user_message

        if context:
            user_content = f"""
Context:
{context}

User question:
{user_message}
"""

        system_message: ChatCompletionSystemMessageParam = {
            "role": "system",
            "content": system_prompt,
        }

        user_message_param: ChatCompletionUserMessageParam = {
            "role": "user",
            "content": user_content,
        }

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                system_message,
                user_message_param,
            ],
        )

        return response.choices[0].message.content or ""