import traceback
import time
from fastapi import Request

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
    http_request: Request,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
):
    print(
        "PRE-HANDLER LATENCY:",
        round(
            time.perf_counter()
            - http_request.state.http_started,
            3,
        ),
        "sec",
        flush=True,
    )

    try:
        user_id = request.user_id
        policy_id = request.policy_id

        if settings.environment == "development":
            if user_id is None and settings.dev_user_id:
                user_id = uuid.UUID(settings.dev_user_id)

            if policy_id is None and settings.dev_policy_id:
                policy_id = uuid.UUID(settings.dev_policy_id)

        handler_started = time.perf_counter()

        answer, conversation_id = await chat_service.generate_answer(
            db=db,
            message=request.message,
            user_id=user_id,
            policy_id=policy_id,
            conversation_id=request.conversation_id,
        )

        print(
            f"API HANDLER TOTAL: "
            f"{time.perf_counter() - handler_started:.3f}s"
        )

        return ChatResponse(
            answer=answer,
            conversation_id=uuid.UUID(str(conversation_id)),
        )



    except Exception as exc:

        print("\n========== CHAT ERROR ==========")

        traceback.print_exc()

        print("================================\n")

        raise HTTPException(

            status_code=503,

            detail="AI service is temporarily unavailable.",

        ) from exc