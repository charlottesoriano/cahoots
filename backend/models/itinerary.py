import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func

if TYPE_CHECKING:
    from models.users import User
    from models.events import Event


class ItineraryItem(SQLModel, table=True):
    __tablename__ = "itinerary_items"

    # uuid, PK
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # uuid, FK → events.id
    event_id: uuid.UUID = Field(foreign_key="events.id", index=True, ondelete="CASCADE")

    # text (not null)
    title: str

    # text, nullable
    description: str | None = Field(default=None)

    # text, nullable
    location: str | None = Field(default=None)

    # float, nullable — for map view
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)

    # int — which day of the trip (0, 1, 2...)
    day_index: int

    # int — position within the day
    sort_order: int

    # timestamptz, nullable
    start_time: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    end_time: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # uuid, FK → users.id
    created_by: str = Field(foreign_key="users.id", index=True)

    # timestamptz, default now()
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    # timestamptz, default now()
    last_updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    # last updated by, nullable
    last_updated_by: str | None = Field(default=None, foreign_key="users.id", index=True)

    # --- connections ---
    event: "Event" = Relationship(back_populates="itinerary_items")
    creator: "User" = Relationship(
        back_populates="itinerary_items_created",
        sa_relationship_kwargs={"foreign_keys": "[ItineraryItem.created_by]"},
    )
    comments: list["ItineraryComment"] = Relationship(
        back_populates="item", cascade_delete=True
    )


class ItineraryComment(SQLModel, table=True):
    """Optional / Phase 2 — threaded comments on an itinerary item."""

    __tablename__ = "itinerary_comments"

    # uuid, PK
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # uuid, FK → itinerary_items.id
    itinerary_item_id: uuid.UUID = Field(
        foreign_key="itinerary_items.id", index=True, ondelete="CASCADE"
    )

    # uuid, FK → users.id
    user_id: str = Field(foreign_key="users.id", index=True)

    # text (not null)
    content: str

    # timestamptz, default now()
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    # --- connections ---
    item: ItineraryItem = Relationship(back_populates="comments")
    user: "User" = Relationship(back_populates="itinerary_comments")
