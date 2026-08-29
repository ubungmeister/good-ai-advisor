from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        primary_key=True,
    )

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))

    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    birth_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        back_populates="profile",
    )