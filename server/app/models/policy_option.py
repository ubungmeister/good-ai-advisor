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
    from app.models.policy import Policy


class PolicyOption(Base):
    __tablename__ = "policy_options"

    __table_args__ = (
        UniqueConstraint(
            "policy_id",
            "code",
            name="uq_policy_options_policy_code",
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

    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    selected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    variant: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    premium_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    currency: Mapped[str | None] = mapped_column(
        String(3),
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