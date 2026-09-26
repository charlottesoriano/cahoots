import uuid
from datetime import date, datetime

from pydantic import BaseModel

# Request body for POST /events. Only the fields a client should be able to
# set — id/created_by/created_at are server-assigned.
class EventCreate(BaseModel):
    title: str
    description: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    cover_image_url: str | None = None

class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    cover_image_url: str | None = None

# Response body — built from the Event ORM object via from_attributes.
class EventRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    location: str | None
    start_date: date | None
    end_date: date | None
    cover_image_url: str | None
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True