from __future__ import annotations

import uuid

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


if TYPE_CHECKING:
    from app.models.coverage_type import CoverageType
    from app.models.plan import Plan


class PlanCoverage(Base):
    __tablename__ = "plan_coverages"

    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "coverage_type_id",
            name="uq_plan_coverages_plan_coverage_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans.id"),
        nullable=False,
    )

    coverage_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coverage_types.id"),
        nullable=False,
    )

    included: Mapped[bool] = mapped_column(
        Boolean,
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

    plan: Mapped[Plan] = relationship()

    coverage_type: Mapped[CoverageType] = relationship()