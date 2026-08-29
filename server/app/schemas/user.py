from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CustomerProfileResponse(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date | None
    phone: str | None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: UUID
    email: str
    status: str
    profile: CustomerProfileResponse | None

    model_config = ConfigDict(from_attributes=True)