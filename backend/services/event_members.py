import uuid
from models.events import EventMember, EventRole
from models.users import User
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from sqlmodel import select
from sqlalchemy.exc import IntegrityError

async def add_member(event_id: uuid.UUID, user: User, role: EventRole, session: AsyncSession) -> EventMember:
    try:
        member = EventMember(event_id=event_id, user_id=user.id, role=role)
        session.add(member)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Already a member of this event")
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to add member to event")

    await session.refresh(member)
    return member

async def is_member(event_id: uuid.UUID, user: User, session: AsyncSession) -> bool:
    result = await session.exec(
        select(EventMember).where(EventMember.event_id == event_id, EventMember.user_id == user.id)
    )
    return result.first() is not None
