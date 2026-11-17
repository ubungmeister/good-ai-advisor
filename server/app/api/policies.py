import uuid

from app.services.policy_service import PolicyService
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.core.identity import get_current_user
from app.models.user import User
from app.schemas.policy import PolicyResponse, PolicyDetailsResponse

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    policy = policy_service.get_policy_for_user(
        db=db,
        policy_id=policy_id,
        user_id=current_user.id,
    )

    if policy is None:
        raise HTTPException(
            status_code=404,
            detail="Policy not found",
        )

    return policy

@router.get(
    "/{policy_id}/details",
    response_model=PolicyDetailsResponse,
)
def get_policy_details(
    policy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    details = policy_service.get_policy_details_for_user(
        db=db,
        policy_id=policy_id,
        user_id=current_user.id,
    )

    if details is None:
        raise HTTPException(
            status_code=404,
            detail="Policy details not found",
        )

    return details

@router.get(
    "",
    response_model=list[PolicyResponse],
)
def get_policies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return policy_service.get_policies_for_user(
        db=db,
        user_id=current_user.id,
    )
