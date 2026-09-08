import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import configure_mappers

import models
from models.availability import AvailabilitySlot
from models.events import Event, EventInvite, EventMember, EventRole
from models.expenses import Expense, ExpenseShare, SplitType
from models.itinerary import ItineraryComment, ItineraryItem
from models.notifications import NotificationLog
from models.packing import PackingItem
from models.polls import Poll, PollOption, PollStatus, PollVote
from models.users import User
from sqlmodel import SQLModel


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


def test_model_package_exports_every_registered_table_and_mappers_configure():
    configure_mappers()

    exported_tables = {
        getattr(models, name).__tablename__
        for name in models.__all__
        if hasattr(getattr(models, name), "__tablename__")
    }

    assert set(SQLModel.metadata.tables) == EXPECTED_TABLES
    assert exported_tables == EXPECTED_TABLES


@pytest.mark.parametrize(
    ("table_name", "column_name", "target", "ondelete"),
    [
        ("availability_slots", "event_id", "events.id", "CASCADE"),
        ("event_invites", "event_id", "events.id", "CASCADE"),
        ("event_members", "event_id", "events.id", "CASCADE"),
        ("expenses", "event_id", "events.id", "CASCADE"),
        ("itinerary_items", "event_id", "events.id", "CASCADE"),
        ("notification_log", "event_id", "events.id", "CASCADE"),
        ("packing_items", "event_id", "events.id", "CASCADE"),
        ("polls", "event_id", "events.id", "CASCADE"),
        ("expense_shares", "expense_id", "expenses.id", "CASCADE"),
        (
            "itinerary_comments",
            "itinerary_item_id",
            "itinerary_items.id",
            "CASCADE",
        ),
        ("poll_options", "poll_id", "polls.id", "CASCADE"),
        ("poll_votes", "poll_option_id", "poll_options.id", "CASCADE"),
    ],
)
def test_owned_records_define_database_cascades(
    table_name, column_name, target, ondelete
):
    foreign_key = next(iter(SQLModel.metadata.tables[table_name].c[column_name].foreign_keys))

    assert foreign_key.target_fullname == target
    assert foreign_key.ondelete == ondelete


def test_parent_relationships_apply_delete_orphan_cascade():
    expected_relationships = {
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
        Expense: {"shares"},
        ItineraryItem: {"comments"},
        Poll: {"options"},
        PollOption: {"votes"},
    }

    for model, relationship_names in expected_relationships.items():
        relationships = inspect(model).relationships
        for name in relationship_names:
            assert "delete" in relationships[name].cascade
            assert "delete-orphan" in relationships[name].cascade


def test_field_defaults_and_optional_boundaries_are_stable():
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()

    event = Event(id=event_id, title="Weekend", created_by=user_id)
    poll = Poll(event_id=event_id, question="When?", created_by=user_id)
    expense = Expense(
        event_id=event_id,
        paid_by=user_id,
        amount=Decimal("12.34"),
        description="Lunch",
        split_type=SplitType.equal,
    )
    packing_item = PackingItem(event_id=event_id, label="Passport")
    notification = NotificationLog(user_id=user_id, type="new_expense")

    assert event.id == event_id
    assert event.description is None
    assert event.start_date is None
    assert poll.id is not None
    assert poll.status is PollStatus.open
    assert poll.closes_at is None
    assert expense.currency == "USD"
    assert packing_item.assigned_to is None
    assert packing_item.is_checked is False
    assert notification.event_id is None


def _add_complete_event_graph(session):
    owner_id = uuid.uuid4()
    guest_id = uuid.uuid4()
    event_id = uuid.uuid4()
    item_id = uuid.uuid4()
    expense_id = uuid.uuid4()
    poll_id = uuid.uuid4()
    option_id = uuid.uuid4()

    session.add_all(
        [
            User(id=owner_id, email="owner@example.com", display_name="Owner"),
            User(id=guest_id, email="guest@example.com", display_name="Guest"),
        ]
    )
    session.flush()
    session.add(Event(id=event_id, title="Weekend", created_by=owner_id))
    session.flush()
    session.add_all(
        [
            EventMember(event_id=event_id, user_id=guest_id, role=EventRole.guest),
            EventInvite(event_id=event_id, token="invite-token", created_by=owner_id),
            ItineraryItem(
                id=item_id,
                event_id=event_id,
                title="Museum",
                day_index=0,
                sort_order=0,
                created_by=owner_id,
            ),
            Expense(
                id=expense_id,
                event_id=event_id,
                paid_by=owner_id,
                amount=Decimal("42.50"),
                description="Tickets",
                split_type=SplitType.custom,
            ),
            Poll(
                id=poll_id,
                event_id=event_id,
                question="Which museum?",
                created_by=owner_id,
            ),
            AvailabilitySlot(
                event_id=event_id,
                user_id=guest_id,
                date=date(2026, 9, 12),
                time_block=47,
            ),
            PackingItem(event_id=event_id, label="Tickets", assigned_to=guest_id),
            NotificationLog(user_id=guest_id, event_id=event_id, type="event_updated"),
        ]
    )
    session.flush()
    session.add_all(
        [
            ItineraryComment(
                itinerary_item_id=item_id, user_id=guest_id, content="Looks good"
            ),
            ExpenseShare(
                expense_id=expense_id, user_id=guest_id, amount_owed=Decimal("21.25")
            ),
            PollOption(id=option_id, poll_id=poll_id, label="Art museum"),
        ]
    )
    session.flush()
    session.add(PollVote(poll_option_id=option_id, user_id=guest_id))
    session.commit()
    return event_id, guest_id, option_id


def test_complete_model_graph_persists_defaults(db_session):
    event_id, _guest_id, _option_id = _add_complete_event_graph(db_session)

    event = db_session.get(Event, event_id)
    expense = db_session.exec(select(Expense)).scalar_one()
    poll = db_session.exec(select(Poll)).scalar_one()
    packing_item = db_session.exec(select(PackingItem)).scalar_one()

    assert event.created_at is not None
    assert expense.amount == Decimal("42.50")
    assert expense.currency == "USD"
    assert poll.status is PollStatus.open
    assert packing_item.is_checked is False


@pytest.mark.parametrize(
    "duplicate_factory",
    [
        lambda event_id, guest_id, _option_id: EventMember(
            event_id=event_id, user_id=guest_id, role=EventRole.organizer
        ),
        lambda _event_id, guest_id, option_id: PollVote(
            poll_option_id=option_id, user_id=guest_id
        ),
    ],
    ids=["event-membership", "poll-vote"],
)
def test_composite_uniqueness_rejects_duplicate_records(db_session, duplicate_factory):
    event_id, guest_id, option_id = _add_complete_event_graph(db_session)
    db_session.add(duplicate_factory(event_id, guest_id, option_id))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_deleting_an_event_cascades_through_all_owned_records(db_session):
    event_id, _guest_id, _option_id = _add_complete_event_graph(db_session)

    db_session.exec(delete(Event).where(Event.id == event_id))
    db_session.commit()

    owned_models = [
        AvailabilitySlot,
        EventInvite,
        EventMember,
        Expense,
        ExpenseShare,
        ItineraryItem,
        ItineraryComment,
        NotificationLog,
        PackingItem,
        Poll,
        PollOption,
        PollVote,
    ]
    remaining = {
        model.__tablename__: db_session.exec(
            select(func.count()).select_from(model)
        ).scalar_one()
        for model in owned_models
    }

    assert remaining == {model.__tablename__: 0 for model in owned_models}
    assert db_session.exec(select(func.count()).select_from(User)).scalar_one() == 2
