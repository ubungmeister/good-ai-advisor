from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

from app.db.dependencies import get_db


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
):
    try:
        answer = await chat_service.generate_answer(
            db=db,
            message=request.message,
        )

        return ChatResponse(
            answer=answer,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="AI service is temporarily unavailable.",
        ) from exc