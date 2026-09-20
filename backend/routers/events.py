from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from sqlalchemy.exc import SQLAlchemyError
from core.security import get_current_user
from database.database import get_session
from models.events import Event, EventMember, EventRole
from models.users import User
from schemas.events import EventCreate, EventRead, EventUpdate
from core.permissions import get_event_member, require_organizer

router = APIRouter(
    prefix="/events",
    tags=["events"],
    dependencies=[Depends(get_current_user)] # only authenticated users can access this router
)

@router.post("/create", response_model=EventRead, status_code=201)
async def create_event(
    payload: EventCreate,
    user: User = Depends(get_current_user), # before the route function is called, call get_current_user and whatever it returns is passed to the route function as the user argument
    session: AsyncSession = Depends(get_session), # before the route function is called, call get_session and whatever it returns is passed to the route function as the session argument
):
    # ** -> dictionary unpacking. SomeClass(**some_dict) -> expands into keyword arguments as if you'd written each key-value pair out by hand:
    # Event(title="Beach trip", description=None, location=None, start_date=None, end_date=None, cover_image_url=None)
    # The model_dump() method converts the EventCreate object into a dictionary, which is then unpacked into the Event constructor.
    # payload.model_dump() -> {'title': 'Beach trip', 'description': None, 'location': None, 'start_date': None, 'end_date': None, 'cover_image_url': None}
    event = Event(**payload.model_dump(), created_by=user.id)

    try:
        session.add(event)
        # flush (not commit) so event.id is assigned before the membership row
        # below references it, while still sharing one transaction with it.
        await session.flush()

        # the creator is automatically the organizer
        session.add(EventMember(event_id=event.id, user_id=user.id, role=EventRole.organizer))

        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to create event")

    await session.refresh(event)
    return event

# events where the current user is a member
# returns a list of events where the current user is a member of
@router.get("/all", response_model=list[EventRead])
async def get_events(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        events = await session.exec(select(Event).where(Event.members.any(user_id=user.id)))
        return events.all()
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Failed to get events")

# event details
@router.get("/{event_id}", response_model=EventRead)
async def get_event_details(
    event_id: str,
    member: EventMember = Depends(get_event_member),
    session: AsyncSession = Depends(get_session),
):
    event = await session.get(
        Event,
        event_id
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return event

# update event
@router.put("/{event_id}", response_model=EventRead)
async def update_event(
    event_id: str,
    payload: EventUpdate,
    member: EventMember = Depends(require_organizer),
    session: AsyncSession = Depends(get_session),
):
    event = await session.get(
        Event,
        event_id,
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event

# delete event
@router.delete("/{event_id}", response_model=EventRead)
async def delete_event(
    event_id: str,
    member: EventMember = Depends(require_organizer),
    session: AsyncSession = Depends(get_session),
):
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    result = EventRead.model_validate(event)
    await session.delete(event)
    await session.commit()
    return result