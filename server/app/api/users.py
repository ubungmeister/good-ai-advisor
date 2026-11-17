from fastapi import APIRouter, Depends
from app.schemas.user import UserResponse
from app.core.identity import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
)


@router.get(
    "/me",
    response_model=UserResponse,
)
def read_current_user(
    user: User = Depends(get_current_user),
):
    return user
