import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

from app.db.dependencies import get_db
import uuid

from app.core.config import settings

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
        user_id = request.user_id
        policy_id = request.policy_id

        if settings.environment == "development":
            if user_id is None and settings.dev_user_id:
                user_id = uuid.UUID(settings.dev_user_id)

            if policy_id is None and settings.dev_policy_id:
                policy_id = uuid.UUID(settings.dev_policy_id)

        answer = await chat_service.generate_answer(
            db=db,
            message=request.message,
            user_id=user_id,
            policy_id=policy_id,
        )

        return ChatResponse(
            answer=answer,
        )



    except Exception as exc:

        print("\n========== CHAT ERROR ==========")

        traceback.print_exc()

        print("================================\n")

        raise HTTPException(

            status_code=503,

            detail="AI service is temporarily unavailable.",

        ) from exc