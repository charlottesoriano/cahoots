import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from models.users import User
    from models.events import Event


class AvailabilitySlot(SQLModel, table=True):
    """Phase 2, When2meet-style — one row per (user, date, 30-min block) they are free."""

    __tablename__ = "availability_slots"

    # uuid, PK
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # uuid, FK → events.id
    event_id: uuid.UUID = Field(foreign_key="events.id", index=True, ondelete="CASCADE")

    # uuid, FK → users.id
    user_id: str = Field(foreign_key="users.id", index=True)

    # date
    date: date

    # int — index representing a 30-min block
    time_block: int

    # --- connections ---
    event: "Event" = Relationship(back_populates="availability_slots")
    user: "User" = Relationship(back_populates="availability_slots")
