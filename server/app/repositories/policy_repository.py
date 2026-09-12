import uuid
from collections.abc import Sequence

from app.models import PolicyCoverage, PolicyOption, TravelPolicyDetail
from sqlalchemy import select, ScalarResult
from sqlalchemy.orm import Session, joinedload

from app.models.policy import Policy
from app.models.policy_person import PolicyPerson

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

    def get_coverages(
            self,
            db: Session,
            policy_id: uuid.UUID,
    ) -> Sequence[PolicyCoverage]:
        return db.scalars(
            select(PolicyCoverage)
            .options(
                joinedload(PolicyCoverage.coverage_type)
            )
            .where(
                PolicyCoverage.policy_id == policy_id
            )
        ).all()
    def get_options(
            self,
            db: Session,
            policy_id: uuid.UUID,
    ) -> Sequence[PolicyOption]:
        return db.scalars(
            select(PolicyOption)
            .where(
                PolicyOption.policy_id == policy_id
            )
        ).all()
    def get_people(
            self,
            db: Session,
            policy_id: uuid.UUID,
    ) -> Sequence[PolicyPerson]:
        return db.scalars(
            select(PolicyPerson)
            .options(
                joinedload(PolicyPerson.person)
            )
            .where(
                PolicyPerson.policy_id == policy_id
            )
        ).all()
    def get_travel_details(
            self,
            db: Session,
            policy_id: uuid.UUID,
    ) -> TravelPolicyDetail | None:
        return db.scalar(
            select(TravelPolicyDetail)
            .where(
                TravelPolicyDetail.policy_id == policy_id
            )
        )