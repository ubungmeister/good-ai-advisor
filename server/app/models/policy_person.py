import uuid
import enum

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    DateTime,
    Date,
    Enum as SqlEnum,
    ForeignKey,
    UniqueConstraint,
)
from datetime import datetime, date
from typing import TYPE_CHECKING


from app.db.database import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.policy import Policy


class PersonRole(str, enum.Enum):
    POLICYHOLDER = "POLICYHOLDER"
    INSURED = "INSURED"



class PolicyPerson(Base):
    __tablename__ = "policy_persons"

    __table_args__ = (
        UniqueConstraint(
            "policy_id",
            "person_id",
            "role",
            name="uq_policy_persons_policy_person_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policies.id"),
        nullable=False,
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id"),
        nullable=False,
    )

    role: Mapped[PersonRole] = mapped_column(
        SqlEnum(
            PersonRole,
            name="person_role",
        ),
        nullable=False,
    )

    coverage_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    coverage_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )