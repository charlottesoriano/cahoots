import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func

if TYPE_CHECKING:
    from models.users import User
    from models.events import Event


class PackingItem(SQLModel, table=True):
    """Phase 3, optional — shared packing list per event."""

    __tablename__ = "packing_items"

    # uuid, PK
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # uuid, FK → events.id
    event_id: uuid.UUID = Field(foreign_key="events.id", index=True, ondelete="CASCADE")

    # text (not null)
    label: str

    # uuid, FK → users.id, nullable — null = shared item
    assigned_to: str | None = Field(
        default=None, foreign_key="users.id", index=True
    )

    # boolean, default false
    is_checked: bool = Field(default=False)

    # timestamptz, default now()
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    # --- connections ---
    event: "Event" = Relationship(back_populates="packing_items")
    assignee: Optional["User"] = Relationship(back_populates="packing_items_assigned")
