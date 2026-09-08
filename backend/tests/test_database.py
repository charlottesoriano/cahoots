import pytest

from database import database


def test_database_url_uses_asyncpg_driver():
    assert database.ASYNC_DATABASE_URL == (
        "postgresql+asyncpg://user:password@localhost/cahoots_test"
    )


@pytest.mark.asyncio
async def test_get_session_yields_bound_session_and_closes_it(monkeypatch):
    created_sessions = []

    class FakeSession:
        def __init__(self, bind):
            self.bind = bind
            self.exited = False
            created_sessions.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            self.exited = True

    monkeypatch.setattr(database, "AsyncSession", FakeSession)
    session_generator = database.get_session()

    yielded_session = await anext(session_generator)

    assert yielded_session is created_sessions[0]
    assert yielded_session.bind is database.engine
    assert not yielded_session.exited

    await session_generator.aclose()

    assert yielded_session.exited
