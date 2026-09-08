from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from core.config import settings

# Supabase gives you a postgresql:// URL — SQLAlchemy's async driver needs
# postgresql+asyncpg:// instead, so swap the prefix
ASYNC_DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

engine = create_async_engine(ASYNC_DATABASE_URL, echo=True)

async def get_session():
    """Provide an asynchronous database session for application operations."""
    async with AsyncSession(engine) as session:
        yield session