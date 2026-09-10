import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.policy import Policy


class PolicyRepository:

    def get_by_id(
        self,
        db: Session,
        policy_id: uuid.UUID,
    ) -> Policy | None:

        return db.scalar(
            select(Policy).where(
                Policy.id == policy_id
            )
        )

    def get_by_policy_number(
        self,
        db: Session,
        policy_number: str,
    ) -> Policy | None:

        return db.scalar(
            select(Policy).where(
                Policy.policy_number == policy_number
            )
        )

    def get_by_owner_user_id(
        self,
        db: Session,
        user_id: uuid.UUID,
    ) -> Sequence[Policy]:

        return db.scalars(
            select(Policy).where(
                Policy.owner_user_id == user_id
            )
        ).all()