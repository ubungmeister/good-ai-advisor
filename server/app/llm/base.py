from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar(
    "T",
    bound=BaseModel,
)


class BaseLLMProvider(ABC):

    @abstractmethod
    async def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str | None = None,
    ) -> str:
        pass

    async def generate_structured(
            self,
            *,
            system_prompt: str,
            user_message: str,
            response_model: type[T],
            context: str | None = None,
    ) -> T:
        pass