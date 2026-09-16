import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, Numeric, func

if TYPE_CHECKING:
    from models.users import User
    from models.events import Event


class SplitType(str, Enum):
    equal = "equal"
    custom = "custom"


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"

    # uuid, PK
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # uuid, FK → events.id
    event_id: uuid.UUID = Field(foreign_key="events.id", index=True, ondelete="CASCADE")

    # uuid, FK → users.id — who fronted the money
    paid_by: str = Field(foreign_key="users.id", index=True)

    # numeric(10,2)
    amount: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))

    # text, default 'USD'
    currency: str = Field(default="USD")

    # text (not null)
    description: str

    # enum('equal','custom')
    split_type: SplitType

    # timestamptz, default now()
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    # --- connections ---
    event: "Event" = Relationship(back_populates="expenses")
    payer: "User" = Relationship(back_populates="expenses_paid")
    shares: list["ExpenseShare"] = Relationship(
        back_populates="expense", cascade_delete=True
    )


class ExpenseShare(SQLModel, table=True):
    __tablename__ = "expense_shares"

    # uuid, PK
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # uuid, FK → expenses.id
    expense_id: uuid.UUID = Field(
        foreign_key="expenses.id", index=True, ondelete="CASCADE"
    )

    # uuid, FK → users.id — who owes this share
    user_id: str = Field(foreign_key="users.id", index=True)

    # numeric(10,2)
    amount_owed: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))

    # --- connections ---
    # NOTE: `settlement` ("who owes who") is computed on the fly from
    # expenses + expense_shares — there is no settlement table.
    expense: Expense = Relationship(back_populates="shares")
    user: "User" = Relationship(back_populates="expense_shares")
