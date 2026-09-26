from fastapi import Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.security import get_current_user
from database.database import get_session
from models.events import EventMember, EventRole
from models.users import User
import uuid

async def get_event_member(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EventMember:
    result = await session.exec(
        select(EventMember).where(
            EventMember.event_id == event_id,
            EventMember.user_id == user.id,
        )
    )
    member = result.first()
    if member is None:
        raise HTTPException(status_code=403, detail="Not a member of this event")
    return member


async def require_organizer(
    member: EventMember = Depends(get_event_member),
) -> EventMember:
    if member.role != EventRole.organizer:
        raise HTTPException(status_code=403, detail="Organizer role required")
    return member
