from fastapi import APIRouter, HTTPException
from services.invites import create_invite, is_valid_token
from services.event_members import add_member
from core.security import get_current_user
from fastapi import Depends
from models.events import EventMember, EventRole
from models.users import User
from database.database import get_session
from sqlmodel.ext.asyncio.session import AsyncSession
from schemas.invites import EventInviteRead
from core.permissions import require_organizer
from sqlmodel import select
import uuid

router = APIRouter(
    prefix="/invites",
    tags=["invites"],
    dependencies=[Depends(get_current_user)] # only authenticated users can access this router
)

# create an invite
@router.post("/{event_id}", response_model=EventInviteRead, status_code=201)
async def create_invite_link(
    event_id: uuid.UUID,
    member: EventMember = Depends(require_organizer),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    invite = await create_invite(event_id, user, session)
    return invite


# accept an invite
# handle: already a member, invalid/expired token
@router.post("/{event_id}/{token}/accept", response_model=EventMember)
async def accept_invite(
    event_id: uuid.UUID,
    token: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await is_valid_token(token, event_id, user, session)
    
    if result.is_member and result.event_id is not None and not result.is_expired:
        # just return the member 
        member = (await session.exec(
            select(EventMember).where(EventMember.event_id == result.event_id, EventMember.user_id == user.id)
        )).first()
        return member

    if result.is_expired:
        raise HTTPException(status_code=410, detail="The invite has expired")
    if result.event_id is None:
        raise HTTPException(status_code=404, detail="The invite is not valid")

    # add the user to the event
    member = await add_member(result.event_id, user, EventRole.guest, session)
    return member