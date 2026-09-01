from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PersonResponse(BaseModel):
    first_name: str | None
    last_name: str | None
    date_of_birth: date | None
    phone: str | None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: UUID
    email: str
    status: str
    person: PersonResponse

    model_config = ConfigDict(from_attributes=True)