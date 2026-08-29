from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return ChatResponse(
        answer=f"You asked: {request.message}"
    )
