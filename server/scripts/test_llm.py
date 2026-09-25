import asyncio
import os

from app.core.config import settings
from dotenv import load_dotenv

from app.llm.providers.groq_provider import GroqProvider
from app.services.llm_service import LLMService


load_dotenv()


async def main():
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL")

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing")

    if not model:
        raise RuntimeError("GROQ_MODEL is missing")

    provider = GroqProvider(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
    )
    llm_service = LLMService(provider=provider)

    answer = await llm_service.generate_answer(
        system_prompt="You are a helpful insurance assistant.",
        user_message="What is travel insurance?",
    )

    print(answer)


if __name__ == "__main__":
    asyncio.run(main())