from __future__ import annotations

import enum
import uuid

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


if TYPE_CHECKING:
    from app.models.policy import Policy


class CoverageMode(str, enum.Enum):
    SINGLE_TRIP = "SINGLE_TRIP"
    ANNUAL_REPEATED = "ANNUAL_REPEATED"
    ANNUAL_LONG_TERM = "ANNUAL_LONG_TERM"


class TerritoryType(str, enum.Enum):
    DOMESTIC = "DOMESTIC"
    EUROPE = "EUROPE"
    WORLD = "WORLD"


class TripPurpose(str, enum.Enum):
    LEISURE = "LEISURE"
    WORK_NON_MANUAL = "WORK_NON_MANUAL"
    WORK_MANUAL = "WORK_MANUAL"


class SportLevel(str, enum.Enum):
    RECREATIONAL = "RECREATIONAL"
    WINTER = "WINTER"
    RISKY = "RISKY"


class TravelPolicyDetail(Base):
    __tablename__ = "travel_policy_details"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policies.id"),
        primary_key=True,
    )

    coverage_mode: Mapped[CoverageMode] = mapped_column(
        SqlEnum(
            CoverageMode,
            name="coverage_mode",
        ),
        nullable=False,
    )

    territory: Mapped[TerritoryType] = mapped_column(
        SqlEnum(
            TerritoryType,
            name="territory_type",
        ),
        nullable=False,
    )

    destination_country_code: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
    )

    trip_purpose: Mapped[TripPurpose | None] = mapped_column(
        SqlEnum(
            TripPurpose,
            name="trip_purpose",
        ),
        nullable=True,
    )

    sport_level: Mapped[SportLevel | None] = mapped_column(
        SqlEnum(
            SportLevel,
            name="sport_level",
        ),
        nullable=True,
    )

    max_single_trip_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    departure_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    return_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    policy: Mapped[Policy] = relationship()