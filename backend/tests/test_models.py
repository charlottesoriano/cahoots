import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import DateTime, Numeric
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import configure_mappers
from sqlmodel import SQLModel, Session, create_engine

import models
from models import (
    AvailabilitySlot,
    Event,
    EventInvite,
    EventMember,
    EventRole,
    Expense,
    ExpenseShare,
    ItineraryComment,
    ItineraryItem,
    NotificationLog,
    PackingItem,
    Poll,
    PollOption,
    PollStatus,
    PollVote,
    SplitType,
    User,
)


EXPECTED_TABLES = {
    "availability_slots",
    "event_invites",
    "event_members",
    "events",
    "expense_shares",
    "expenses",
    "itinerary_comments",
    "itinerary_items",
    "notification_log",
    "packing_items",
    "poll_options",
    "poll_votes",
    "polls",
    "users",
}


def _model_factories():
    return [
        lambda: Event(title="Trip", created_by=uuid.uuid4()),
        lambda: EventMember(
            event_id=uuid.uuid4(), user_id=uuid.uuid4(), role=EventRole.guest
        ),
        lambda: EventInvite(
            event_id=uuid.uuid4(), token="token", created_by=uuid.uuid4()
        ),
        lambda: ItineraryItem(
            event_id=uuid.uuid4(),
            title="Museum",
            day_index=0,
            sort_order=0,
            created_by=uuid.uuid4(),
        ),
        lambda: ItineraryComment(
            itinerary_item_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            content="Looks good",
        ),
        lambda: Expense(
            event_id=uuid.uuid4(),
            paid_by=uuid.uuid4(),
            amount=Decimal("12.50"),
            description="Lunch",
            split_type=SplitType.equal,
        ),
        lambda: ExpenseShare(
            expense_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            amount_owed=Decimal("6.25"),
        ),
        lambda: Poll(
            event_id=uuid.uuid4(), question="When?", created_by=uuid.uuid4()
        ),
        lambda: PollOption(poll_id=uuid.uuid4(), label="Saturday"),
        lambda: PollVote(poll_option_id=uuid.uuid4(), user_id=uuid.uuid4()),
        lambda: AvailabilitySlot(
            event_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            date=date(2026, 9, 8),
            time_block=0,
        ),
        lambda: PackingItem(event_id=uuid.uuid4(), label="Passport"),
        lambda: NotificationLog(user_id=uuid.uuid4(), type="new_expense"),
    ]


def test_models_package_registers_and_exports_every_table():
    assert set(SQLModel.metadata.tables) == EXPECTED_TABLES
    assert set(models.__all__) == {
        "User",
        "Event",
        "EventMember",
        "EventInvite",
        "EventRole",
        "ItineraryItem",
        "ItineraryComment",
        "Expense",
        "ExpenseShare",
        "SplitType",
        "Poll",
        "PollOption",
        "PollVote",
        "PollStatus",
        "AvailabilitySlot",
        "PackingItem",
        "NotificationLog",
    }


@pytest.mark.parametrize("factory", _model_factories())
def test_model_ids_are_generated_as_unique_uuids(factory):
    first = factory()
    second = factory()

    assert isinstance(first.id, uuid.UUID)
    assert first.id != second.id


def test_user_id_has_no_generated_default():
    assert User.__table__.c.id.default is None


def test_domain_defaults_are_applied_when_models_are_created():
    event = Event(title="Trip", created_by=uuid.uuid4())
    expense = Expense(
        event_id=event.id,
        paid_by=uuid.uuid4(),
        amount=Decimal("10.00"),
        description="Taxi",
        split_type=SplitType.equal,
    )
    poll = Poll(event_id=event.id, question="Where?", created_by=uuid.uuid4())
    item = PackingItem(event_id=event.id, label="Passport")

    assert event.description is None
    assert event.start_date is None
    assert expense.currency == "USD"
    assert poll.status is PollStatus.open
    assert item.assigned_to is None
    assert item.is_checked is False


@pytest.mark.parametrize(
    ("table_name", "column_name"),
    [
        ("availability_slots", "event_id"),
        ("event_invites", "event_id"),
        ("event_members", "event_id"),
        ("expenses", "event_id"),
        ("itinerary_items", "event_id"),
        ("notification_log", "event_id"),
        ("packing_items", "event_id"),
        ("polls", "event_id"),
        ("expense_shares", "expense_id"),
        ("itinerary_comments", "itinerary_item_id"),
        ("poll_options", "poll_id"),
        ("poll_votes", "poll_option_id"),
    ],
)
def test_owned_rows_have_database_cascade_delete(table_name, column_name):
    foreign_key = next(iter(SQLModel.metadata.tables[table_name].c[column_name].foreign_keys))

    assert foreign_key.ondelete == "CASCADE"


def test_unique_membership_and_vote_constraints_are_declared():
    membership_constraints = {
        constraint.name: {column.name for column in constraint.columns}
        for constraint in EventMember.__table__.constraints
    }
    vote_constraints = {
        constraint.name: {column.name for column in constraint.columns}
        for constraint in PollVote.__table__.constraints
    }

    assert membership_constraints["uq_event_member"] == {"event_id", "user_id"}
    assert vote_constraints["uq_poll_vote"] == {"poll_option_id", "user_id"}
    assert any(index.unique for index in User.__table__.c.email.table.indexes)
    assert any(index.unique for index in EventInvite.__table__.c.token.table.indexes)


def test_money_columns_preserve_two_decimal_places():
    for column in (Expense.__table__.c.amount, ExpenseShare.__table__.c.amount_owed):
        assert isinstance(column.type, Numeric)
        assert column.type.precision == 10
        assert column.type.scale == 2
        assert not column.nullable


@pytest.mark.parametrize(
    ("table_name", "column_name"),
    [
        ("users", "created_at"),
        ("events", "created_at"),
        ("event_members", "joined_at"),
        ("event_invites", "created_at"),
        ("itinerary_items", "created_at"),
        ("itinerary_comments", "created_at"),
        ("expenses", "created_at"),
        ("polls", "created_at"),
        ("poll_votes", "created_at"),
        ("packing_items", "created_at"),
        ("notification_log", "sent_at"),
    ],
)
def test_audit_timestamps_are_timezone_aware_and_server_generated(
    table_name, column_name
):
    column = SQLModel.metadata.tables[table_name].c[column_name]

    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
    assert str(column.server_default.arg) == "now()"
    assert not column.nullable


def test_parent_relationships_delete_owned_children():
    configure_mappers()
    relationships = {
        Event: {
            "members",
            "invites",
            "itinerary_items",
            "expenses",
            "polls",
            "availability_slots",
            "packing_items",
            "notifications",
        },
        ItineraryItem: {"comments"},
        Expense: {"shares"},
        Poll: {"options"},
        PollOption: {"votes"},
    }

    for model, relationship_names in relationships.items():
        for relationship_name in relationship_names:
            cascade = model.__mapper__.relationships[relationship_name].cascade
            assert "delete" in cascade
            assert "delete-orphan" in cascade


def test_database_rejects_duplicate_event_memberships():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    user = User(id=uuid.uuid4(), email="member@example.com", display_name="Member")
    event = Event(title="Trip", created_by=user.id)

    with Session(engine) as session:
        session.add_all([user, event])
        session.commit()
        session.add(
            EventMember(event_id=event.id, user_id=user.id, role=EventRole.organizer)
        )
        session.commit()
        session.add(EventMember(event_id=event.id, user_id=user.id, role=EventRole.guest))

        with pytest.raises(IntegrityError):
            session.commit()


def test_database_rejects_duplicate_votes_for_the_same_option():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    user = User(id=uuid.uuid4(), email="voter@example.com", display_name="Voter")
    event = Event(title="Trip", created_by=user.id)
    poll = Poll(event_id=event.id, question="When?", created_by=user.id)
    option = PollOption(poll_id=poll.id, label="Saturday")

    with Session(engine) as session:
        session.add_all([user, event, poll, option])
        session.commit()
        session.add(PollVote(poll_option_id=option.id, user_id=user.id))
        session.commit()
        session.add(PollVote(poll_option_id=option.id, user_id=user.id))

        with pytest.raises(IntegrityError):
            session.commit()
