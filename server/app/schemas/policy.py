import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.policy import PaymentStatus, PolicyStatus

class CoverageTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str


class PolicyCoverageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    limit_amount: Decimal | None
    currency: str | None

    coverage_type: CoverageTypeResponse

class PolicyOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    selected: bool
    variant: str | None
    currency: str | None

class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str


class PolicyPersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    person: PersonResponse

class TravelPolicyDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    coverage_mode: str
    territory_type: str
    destination_country: str | None
    trip_purpose: str | None
    sport_level: str | None

class PolicyDetailsResponse(BaseModel):
    policy: PolicyResponse
    coverages: list[PolicyCoverageResponse]
    options: list[PolicyOptionResponse]
    people: list[PolicyPersonResponse]
    travel_details: TravelPolicyDetailResponse | None

class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_number: str

    policy_status: PolicyStatus
    payment_status: PaymentStatus

    start_date: date
    end_date: date

    premium_amount: Decimal | None
    currency: str | None

    paid_at: datetime | None