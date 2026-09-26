import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from models import Event, EventInvite, User
from schemas.invites import EventInviteValidate
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from services.event_members import is_member

# create a random token
def create_random_token() -> str:
    return secrets.token_urlsafe(32)


# check in event_invites if:
# the token is valid
# the token is not expired or the event has ended
# the token is for the correct event
# the user is already a member of the event
async def is_valid_token(token: str, event_id: uuid.UUID, current_user: User, session: AsyncSession) -> EventInviteValidate:
    invite = (await session.exec(
        select(EventInvite).where(EventInvite.token == token, EventInvite.event_id == event_id)
    )).first()

    if invite is None:
        return EventInviteValidate(token=token, event_id=None, is_valid=False, is_expired=False, is_member=False)

    expired = await is_expired(invite, session)
    if expired:
        return EventInviteValidate(token=token, event_id=invite.event_id, expires_at=invite.expires_at, is_valid=False, is_expired=True, is_member=False)

    member = await is_member(invite.event_id, current_user, session)
    if member:
        return EventInviteValidate(token=token, event_id=invite.event_id, expires_at=invite.expires_at, is_valid=False, is_expired=False, is_member=True)

    return EventInviteValidate(token=token, event_id=invite.event_id, expires_at=invite.expires_at, is_valid=True, is_expired=False, is_member=False)

async def is_expired(invite: EventInvite, session: AsyncSession) -> bool:
    now = datetime.now(timezone.utc)
    event = await session.get(Event, invite.event_id)
    return (invite.expires_at is not None and invite.expires_at < now) or \
            (event.end_date is not None and event.end_date < now.date())

async def create_invite(event_id: uuid.UUID, current_user: User, session: AsyncSession) -> EventInvite:
    try:
        token = create_random_token()
        # will expire 24 hours after the invite is created
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        invite = EventInvite(event_id=event_id, token=token, created_by=current_user.id, expires_at=expires_at)
        session.add(invite)
        await session.commit()
        await session.refresh(invite)
        return invite
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to create an invite link.")