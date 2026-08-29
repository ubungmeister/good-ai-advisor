from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.policy import Policy
from app.models.product_version import ProductVersion


def get_policies_by_user_id(
    db: Session,
    user_id: UUID,
) -> list[Policy]:
    statement = (
        select(Policy)
        .options(
            joinedload(Policy.product_version)
            .joinedload(ProductVersion.product)
        )
        .where(Policy.user_id == user_id)
        .order_by(Policy.start_date.desc())
    )

    return list(
        db.scalars(statement).all()
    )


def get_policy_by_id_for_user(
    db: Session,
    policy_id: UUID,
    user_id: UUID,
) -> Policy | None:
    statement = (
        select(Policy)
        .options(
            joinedload(Policy.product_version)
            .joinedload(ProductVersion.product)
        )
        .where(
            Policy.id == policy_id,
            Policy.user_id == user_id,
        )
    )

    return db.scalar(statement)