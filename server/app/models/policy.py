from __future__ import annotations

import enum
import uuid

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


if TYPE_CHECKING:
    from app.models.plan import Plan
    from app.models.product_version import ProductVersion
    from app.models.user import User


class PolicyStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class PaymentStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    PAID = "PAID"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    product_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_versions.id"),
        nullable=False,
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans.id"),
        nullable=False,
    )

    policy_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    policy_status: Mapped[PolicyStatus] = mapped_column(
        SqlEnum(
            PolicyStatus,
            name="policy_status",
        ),
        nullable=False,
    )

    payment_status: Mapped[PaymentStatus] = mapped_column(
        SqlEnum(
            PaymentStatus,
            name="payment_status",
        ),
        nullable=False,
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    premium_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    owner: Mapped[User] = relationship()

    product_version: Mapped[ProductVersion] = relationship()

    plan: Mapped[Plan] = relationship()