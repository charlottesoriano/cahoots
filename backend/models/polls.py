import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
from sqlalchemy import Column, DateTime, func

if TYPE_CHECKING:
    from models.users import User
    from models.events import Event


class PollStatus(str, Enum):
    open = "open"
    closed = "closed"


class Poll(SQLModel, table=True):
    __tablename__ = "polls"

    # uuid, PK
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # uuid, FK → events.id
    event_id: uuid.UUID = Field(foreign_key="events.id", index=True, ondelete="CASCADE")

    # text — e.g. "Which weekend works?"
    question: str

    # enum('open','closed')
    status: PollStatus = Field(default=PollStatus.open)

    # uuid, FK → users.id
    created_by: uuid.UUID = Field(foreign_key="users.id", index=True)

    # timestamptz, nullable
    closes_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # timestamptz, default now()
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    # --- connections ---
    event: "Event" = Relationship(back_populates="polls")
    creator: "User" = Relationship(back_populates="polls_created")
    options: list["PollOption"] = Relationship(
        back_populates="poll", cascade_delete=True
    )


class PollOption(SQLModel, table=True):
    __tablename__ = "poll_options"

    # uuid, PK
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # uuid, FK → polls.id
    poll_id: uuid.UUID = Field(foreign_key="polls.id", index=True, ondelete="CASCADE")

    # text — e.g. "Sept 12-14"
    label: str

    # --- connections ---
    poll: Poll = Relationship(back_populates="options")
    votes: list["PollVote"] = Relationship(
        back_populates="option", cascade_delete=True
    )


class PollVote(SQLModel, table=True):
    __tablename__ = "poll_votes"
    # one vote per user per option; app layer enforces "one vote per poll"
    # if that is the desired rule (poll_id is not on this row).
    __table_args__ = (
        UniqueConstraint("poll_option_id", "user_id", name="uq_poll_vote"),
    )

    # uuid, PK
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # uuid, FK → poll_options.id
    poll_option_id: uuid.UUID = Field(
        foreign_key="poll_options.id", index=True, ondelete="CASCADE"
    )

    # uuid, FK → users.id
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    # timestamptz, default now()
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    # --- connections ---
    option: PollOption = Relationship(back_populates="votes")
    user: "User" = Relationship(back_populates="poll_votes")
