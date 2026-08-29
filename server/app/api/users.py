from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.dependencies import get_db
from app.schemas.user import UserResponse
from app.services.user_service import get_current_user

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
)


@router.get(
    "/me",
    response_model=UserResponse,
)
def read_current_user(
    db: Session = Depends(get_db),
):
    user = get_current_user(db)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return user