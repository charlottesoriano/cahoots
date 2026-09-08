import os
import re
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).parents[1]
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


def _run_offline_migration(*arguments):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql://user:password@localhost/cahoots_test"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments, "--sql"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_initial_migration_compiles_complete_postgresql_schema():
    result = _run_offline_migration("upgrade", "head")

    assert result.returncode == 0, result.stderr
    created_tables = set(re.findall(r"CREATE TABLE ([a-z_]+)", result.stdout))
    assert created_tables == EXPECTED_TABLES | {"alembic_version"}
    assert "CONSTRAINT uq_event_member UNIQUE (event_id, user_id)" in result.stdout
    assert "CONSTRAINT uq_poll_vote UNIQUE (poll_option_id, user_id)" in result.stdout
    assert "NUMERIC(10, 2)" in result.stdout
    assert "ON DELETE CASCADE" in result.stdout


def test_initial_migration_downgrade_compiles_removal_of_every_domain_table():
    result = _run_offline_migration("downgrade", "218ce2d09b92:base")

    assert result.returncode == 0, result.stderr
    dropped_tables = set(re.findall(r"DROP TABLE ([a-z_]+)", result.stdout))
    assert dropped_tables == EXPECTED_TABLES
