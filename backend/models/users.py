from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func

if TYPE_CHECKING:
    from models.events import Event, EventMember, EventInvite
    from models.itinerary import ItineraryItem, ItineraryComment
    from models.expenses import Expense, ExpenseShare
    from models.polls import Poll, PollVote
    from models.availability import AvailabilitySlot
    from models.packing import PackingItem
    from models.notifications import NotificationLog


class User(SQLModel, table=True):
    __tablename__ = "users"

    # uuid, PK — "matches Clerk/Supabase Auth user id"
    # No default_factory: the id comes FROM Clerk/Supabase Auth, you pass it in
    # when you create the row (in the signup sync webhook, Phase 1).
    id: str = Field(primary_key=True)

    # text, unique
    email: str = Field(unique=True, index=True)

    # text (not null)
    display_name: str

    # text, nullable
    avatar_url: str | None = Field(default=None)

    # text, nullable — Expo push token
    push_token: str | None = Field(default=None)

    # timestamptz, default now() — set by Postgres, not Python
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    # --- connections ---
    # Events the user created (events.created_by)
    events_created: list["Event"] = Relationship(
        back_populates="creator",
        sa_relationship_kwargs={"foreign_keys": "[Event.created_by]"},
    )
    # Rows joining the user to events they belong to (event_members.user_id)
    event_memberships: list["EventMember"] = Relationship(back_populates="user")
    # Invite links the user generated (event_invites.created_by)
    event_invites_created: list["EventInvite"] = Relationship(back_populates="creator")
    # Itinerary items the user added (itinerary_items.created_by)
    itinerary_items_created: list["ItineraryItem"] = Relationship(
        back_populates="creator",
        sa_relationship_kwargs={"foreign_keys": "[ItineraryItem.created_by]"},
    )
    # Comments the user left on itinerary items (itinerary_comments.user_id)
    itinerary_comments: list["ItineraryComment"] = Relationship(back_populates="user")
    # Expenses the user fronted (expenses.paid_by)
    expenses_paid: list["Expense"] = Relationship(back_populates="payer")
    # Shares the user owes (expense_shares.user_id)
    expense_shares: list["ExpenseShare"] = Relationship(back_populates="user")
    # Polls the user created (polls.created_by)
    polls_created: list["Poll"] = Relationship(back_populates="creator")
    # Poll votes the user cast (poll_votes.user_id)
    poll_votes: list["PollVote"] = Relationship(back_populates="user")
    # Availability the user marked (availability_slots.user_id)
    availability_slots: list["AvailabilitySlot"] = Relationship(back_populates="user")
    # Packing items assigned to the user (packing_items.assigned_to)
    packing_items_assigned: list["PackingItem"] = Relationship(back_populates="assignee")
    # Notifications sent to the user (notification_log.user_id)
    notifications: list["NotificationLog"] = Relationship(back_populates="user")
