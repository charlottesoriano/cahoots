import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func

if TYPE_CHECKING:
    from models.users import User
    from models.events import Event


class NotificationLog(SQLModel, table=True):
    """Optional — a log of push notifications sent, handy for debugging."""

    __tablename__ = "notification_log"

    # uuid, PK
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # uuid, FK → users.id — the recipient
    user_id: str = Field(foreign_key="users.id", index=True)

    # uuid, FK → events.id, nullable — not every notification is event-scoped
    event_id: uuid.UUID | None = Field(
        default=None, foreign_key="events.id", index=True, ondelete="CASCADE"
    )

    # text — e.g. 'new_expense', 'poll_closing'
    type: str

    # timestamptz, default now()
    sent_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    # --- connections ---
    user: "User" = Relationship(back_populates="notifications")
    event: Optional["Event"] = Relationship(back_populates="notifications")
