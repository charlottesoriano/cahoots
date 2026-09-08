import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


migration = importlib.import_module(
    "migrations.versions.20260907_2118-218ce2d09b92_initial_schema"
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


def test_initial_migration_revision_metadata():
    assert migration.revision == "218ce2d09b92"
    assert migration.down_revision is None
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_initial_migration_upgrades_and_downgrades_the_complete_schema(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)

        migration.upgrade()

        schema = inspect(connection)
        assert set(schema.get_table_names()) == EXPECTED_TABLES
        assert {constraint["name"] for constraint in schema.get_unique_constraints("event_members")} == {
            "uq_event_member"
        }
        assert {constraint["name"] for constraint in schema.get_unique_constraints("poll_votes")} == {
            "uq_poll_vote"
        }
        event_foreign_key = next(
            foreign_key
            for foreign_key in schema.get_foreign_keys("event_members")
            if foreign_key["constrained_columns"] == ["event_id"]
        )
        assert event_foreign_key["referred_table"] == "events"
        assert event_foreign_key["options"]["ondelete"] == "CASCADE"

        migration.downgrade()

        assert inspect(connection).get_table_names() == []
    engine.dispose()
