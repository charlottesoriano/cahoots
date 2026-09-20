import uuid
from datetime import datetime
from pydantic import BaseModel

class ItineraryCreate(BaseModel):
    title: str
    description: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    day_index: int
    sort_order: int
    start_time: datetime | None = None
    end_time: datetime | None = None

class ItineraryUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    day_index: int | None = None
    sort_order: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

class ItineraryRead(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    title: str
    description: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    day_index: int
    sort_order: int
    start_time: datetime | None = None
    end_time: datetime | None = None
    created_by: str
    created_at: datetime
    last_updated_by: str | None = None
    last_updated_at: datetime | None = None

    class Config:
        from_attributes = True

class ItineraryUpdateOrder(BaseModel):
    itinerary_id: uuid.UUID
    sort_order: int

