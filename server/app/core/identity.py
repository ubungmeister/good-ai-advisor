"""Server-controlled local demo identity, pending production authentication."""

import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.dependencies import get_db
from app.models.user import User
from app.repositories.user_repository import get_user_by_id


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    # Never fall back to demo identity in a deployed environment.
    if settings.environment != "development":
        raise HTTPException(status_code=401, detail="Authentication is required.")

    if "user_id" in request.query_params:
        raise HTTPException(status_code=400, detail="Client-selected identity is not supported.")

    try:
        user_id = uuid.UUID(settings.dev_user_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=503, detail="Demo identity is not configured.") from None

    user = get_user_by_id(db=db, user_id=user_id)
    if user is None or user.status != "ACTIVE":
        raise HTTPException(status_code=401, detail="An active user is required.")
    return user
