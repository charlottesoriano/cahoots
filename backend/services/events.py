import uuid
from models import Event
from sqlmodel.ext.asyncio.session import AsyncSession


async def is_event_valid(event_id: uuid.UUID, session: AsyncSession) -> bool:
    event = await session.get(Event, event_id)
    return event is not None
