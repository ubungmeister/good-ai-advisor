from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.user import User


def get_user_by_id(
    db: Session,
    user_id: UUID,
) -> User | None:
    statement = (
        select(User)
        .options(joinedload(User.person))
        .where(User.id == user_id)
    )

    return db.scalar(statement)


def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    statement = (
        select(User)
        .options(joinedload(User.person))
        .where(User.email == email)
    )

    return db.scalar(statement)