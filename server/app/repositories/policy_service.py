import uuid

from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.services.policy_service import PolicyRepository


class PolicyService:

    def __init__(self):
        self.policy_repository = PolicyRepository()

    def get_policy_for_user(
        self,
        db: Session,
        policy_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Policy | None:

        policy = self.policy_repository.get_by_id(
            db=db,
            policy_id=policy_id,
        )

        print("REQUESTED POLICY ID:", policy_id)
        print("FOUND POLICY:", policy)

        if policy is None:
            print("POLICY NOT FOUND IN DATABASE")
            return None

        print("POLICY OWNER:", policy.owner_user_id)
        print("REQUESTED USER:", user_id)

        if policy.owner_user_id != user_id:
            print("USER DOES NOT OWN THIS POLICY")
            return None

        return policy