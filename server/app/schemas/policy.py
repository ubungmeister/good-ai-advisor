import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.policy import PaymentStatus, PolicyStatus


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