from fastapi import APIRouter, Depends

from app.core.dependencies import get_llm_service
from app.services.llm_service import LLMService


router = APIRouter(
    prefix="/api/llm",
    tags=["LLM"],
)


@router.get("/test")
async def test_llm(
    llm_service: LLMService = Depends(get_llm_service),
):
    answer = await llm_service.generate_answer(
        system_prompt="You are a helpful insurance assistant.",
        user_message="What is travel insurance?",
    )

    return {
        "answer": answer,
    }