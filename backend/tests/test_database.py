import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import database.database as database


def test_database_url_uses_the_asyncpg_driver():
    assert database.ASYNC_DATABASE_URL.startswith("postgresql+asyncpg://")
    assert database.engine.url.drivername == "postgresql+asyncpg"


@pytest.mark.asyncio
async def test_get_session_yields_and_closes_an_async_session(monkeypatch):
    yielded_session = object()

    class SessionContext:
        entered = False
        exited = False

        async def __aenter__(self):
            self.entered = True
            return yielded_session

        async def __aexit__(self, exc_type, exc, traceback):
            self.exited = True

    context = SessionContext()

    def session_factory(engine):
        assert engine is database.engine
        return context

    monkeypatch.setattr(database, "AsyncSession", session_factory)
    session_dependency = database.get_session()

    assert await anext(session_dependency) is yielded_session
    assert context.entered is True

    await session_dependency.aclose()

    assert context.exited is True


@pytest.mark.asyncio
async def test_get_session_returns_the_expected_session_type():
    session_dependency = database.get_session()
    session = await anext(session_dependency)
    try:
        assert isinstance(session, AsyncSession)
        assert session.bind is database.engine
    finally:
        await session_dependency.aclose()
