import uuid

from app.models import PolicyCoverage, PolicyOption, PolicyPerson, TravelPolicyDetail
from sqlalchemy.orm import Session
from collections.abc import Sequence

from app.models.policy import Policy
from app.repositories.policy_repository import PolicyRepository


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

    def get_policy_coverages_for_user(
            self,
            db: Session,
            policy_id: uuid.UUID,
            user_id: uuid.UUID,
    ) -> Sequence[PolicyCoverage]:

        policy = self.get_policy_for_user(
            db=db,
            policy_id=policy_id,
            user_id=user_id,
        )

        if policy is None:
            return []

        return self.policy_repository.get_coverages(
            db=db,
            policy_id=policy.id,
        )
    def get_policy_options_for_user(
            self,
            db: Session,
            policy_id: uuid.UUID,
            user_id: uuid.UUID,
    ) -> Sequence[PolicyOption]:

        policy = self.get_policy_for_user(
            db=db,
            policy_id=policy_id,
            user_id=user_id,
        )

        if policy is None:
            return []

        return self.policy_repository.get_options(
            db=db,
            policy_id=policy.id,
        )

    def get_policy_people_for_user(
            self,
            db: Session,
            policy_id: uuid.UUID,
            user_id: uuid.UUID,
    ) -> Sequence[PolicyPerson]:

        policy = self.get_policy_for_user(
            db=db,
            policy_id=policy_id,
            user_id=user_id,
        )

        if policy is None:
            return []

        return self.policy_repository.get_people(
            db=db,
            policy_id=policy.id,
        )

    def get_policy_travel_details_for_user(
            self,
            db: Session,
            policy_id: uuid.UUID,
            user_id: uuid.UUID,
    ) -> TravelPolicyDetail | None:

        policy = self.get_policy_for_user(
            db=db,
            policy_id=policy_id,
            user_id=user_id,
        )

        if policy is None:
            return None

        return self.policy_repository.get_travel_details(
            db=db,
            policy_id=policy.id,
        )

    def get_policy_details_for_user(
            self,
            db: Session,
            policy_id: uuid.UUID,
            user_id: uuid.UUID,
    ):
        policy = self.get_policy_for_user(
            db=db,
            policy_id=policy_id,
            user_id=user_id,
        )

        if policy is None:
            return None

        coverages = self.policy_repository.get_coverages(
            db=db,
            policy_id=policy.id,
        )

        options = self.policy_repository.get_options(
            db=db,
            policy_id=policy.id,
        )

        people = self.policy_repository.get_people(
            db=db,
            policy_id=policy.id,
        )

        travel_details = self.policy_repository.get_travel_details(
            db=db,
            policy_id=policy.id,
        )

        return {
            "policy": policy,
            "coverages": coverages,
            "options": options,
            "people": people,
            "travel_details": travel_details,
        }

    def get_policies_for_user(
            self,
            db: Session,
            user_id: uuid.UUID,
    ) -> Sequence[Policy]:

        return self.policy_repository.get_by_owner_user_id(
            db=db,
            user_id=user_id,
        )