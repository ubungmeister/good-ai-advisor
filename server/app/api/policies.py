import uuid

from app.repositories.policy_service import PolicyService
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.policy import PolicyResponse


router = APIRouter(
    prefix="/api/policies",
    tags=["policies"],
)

policy_service = PolicyService()


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
)
def get_policy(
    policy_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    policy = policy_service.get_policy_for_user(
        db=db,
        policy_id=policy_id,
        user_id=user_id,
    )

    if policy is None:
        raise HTTPException(
            status_code=404,
            detail="Policy not found",
        )

    return policy