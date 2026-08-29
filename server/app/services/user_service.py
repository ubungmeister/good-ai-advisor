from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import get_user_by_email


TEST_USER_EMAIL = "test@example.com"


def get_current_user(
    db: Session,
) -> User | None:
    return get_user_by_email(
        db=db,
        email=TEST_USER_EMAIL,
    )
