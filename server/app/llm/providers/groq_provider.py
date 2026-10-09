from groq import AsyncGroq
from groq.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
import json

from app.llm.base import BaseLLMProvider

from typing import TypeVar
from pydantic import BaseModel

T = TypeVar(
    "T",
    bound=BaseModel,
)

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

    async def generate_structured(
            self,
            *,
            system_prompt: str,
            user_message: str,
            response_model: type[T],
            context: str | None = None,
    ) -> T:

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
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": False,
                    "schema": response_model.model_json_schema(),
                },
            },
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                "LLM returned an empty structured response."
            )

        data = json.loads(content)

        return response_model.model_validate(data)