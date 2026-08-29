from fastapi import APIRouter, HTTPException

from app.ai.service import generate_answer
from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        answer = await generate_answer(request.message)

        return ChatResponse(
            answer=answer
        )

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="AI service is temporarily unavailable."
        )