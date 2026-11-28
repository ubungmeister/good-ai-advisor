import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_chat_service
from app.core.identity import get_current_user
from app.db.dependencies import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.access_errors import ResourceNotFoundError
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
):
    print(f"[CHAT] USER QUESTION: {request.message}", flush=True)

    policy_id = request.policy_id
    # Only a new conversation may inherit the server's demo policy.
    if (request.conversation_id is None and policy_id is None
            and settings.environment == "development" and settings.dev_policy_id):
        try:
            policy_id = uuid.UUID(settings.dev_policy_id)
        except ValueError:
            raise HTTPException(status_code=503, detail="Demo policy is not configured.") from None

    started = time.perf_counter()
    try:
        answer, conversation_id = await chat_service.generate_answer(
            db=db,
            message=request.message,
            user_id=current_user.id,
            policy_id=policy_id,
            conversation_id=request.conversation_id,
        )
        return ChatResponse(answer=answer, conversation_id=conversation_id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Resource not found.") from None
    except HTTPException:
        raise
    except Exception:
        # Exception messages/tracebacks can include prompts, IDs or SQL parameters.
        logger.error("Chat request failed.")
        raise HTTPException(
            status_code=503, detail="AI service is temporarily unavailable.",
        ) from None
    finally:
        logger.info("Chat request completed in %.3f seconds.", time.perf_counter() - started)
