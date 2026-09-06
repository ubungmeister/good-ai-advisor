from __future__ import annotations

import uuid

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


if TYPE_CHECKING:
    from app.models.coverage_type import CoverageType
    from app.models.plan_coverage import PlanCoverage
    from app.models.policy import Policy
    from app.models.policy_person import PolicyPerson



class PolicyCoverage(Base):
    __tablename__ = "policy_coverages"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policies.id"),
        nullable=False,
    )

    coverage_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coverage_types.id"),
        nullable=False,
    )

    policy_person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policy_persons.id"),
        nullable=True,
    )

    source_plan_coverage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plan_coverages.id"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="ACTIVE",
        nullable=False,
    )

    limit_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )

    coverage_level: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    deductible_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    deductible_value: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    parameters: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    policy: Mapped[Policy] = relationship()

    coverage_type: Mapped[CoverageType] = relationship()

    policy_person: Mapped[PolicyPerson | None] = relationship()

    source_plan_coverage: Mapped[PlanCoverage | None] = relationship()