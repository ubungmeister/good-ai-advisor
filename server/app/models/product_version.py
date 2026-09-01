from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from app.models.plan import Plan
from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.plan import Plan
    from app.models.product import Product


class ProductVersion(Base):
    __tablename__ = "product_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )

    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    valid_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    valid_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    product: Mapped[Product] = relationship(
        back_populates="versions"
    )

    plans: Mapped[list[Plan]] = relationship(
        back_populates="product_version",
    )