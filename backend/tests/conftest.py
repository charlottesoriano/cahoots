import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlmodel import SQLModel, Session


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

# Modules create the async engine while they are imported. Keep tests isolated from
# external services while still exercising the URL conversion used in production.
os.environ.setdefault(
    "DATABASE_URL", "postgresql://test_user:test_password@localhost/cahoots_test"
)
os.environ.setdefault(
    "ALLOWED_ORIGINS", "https://app.example.com, https://admin.example.com"
)


@pytest.fixture
def db_session():
    import models  # noqa: F401 - register every model before creating the schema

    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()
