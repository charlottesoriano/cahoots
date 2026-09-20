from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from core.permissions import get_event_member, require_organizer
from database.database import get_session
from models import EventMember, ItineraryItem
from schemas.itineraries import ItineraryCreate, ItineraryRead, ItineraryUpdate, ItineraryUpdateOrder
from core.security import get_current_user
from fastapi import Depends

router = APIRouter(
    prefix="/itinerary",
    tags=["itinerary"],
    dependencies=[Depends(get_current_user)] # only authenticated users can access this router
)

# get itineraries for the event (for organizer or guest)
@router.get("/{event_id}", response_model=list[ItineraryRead])
async def get_itineraries_for_event(
    event_id: str,
    member: EventMember = Depends(get_event_member),
    session: AsyncSession = Depends(get_session),
):
    itineraries = await session.execute(
        select(ItineraryItem).where(ItineraryItem.event_id == event_id)
    )
    # order by day_index and sort_order
    itineraries = sorted(itineraries.scalars().all(), key=lambda x: (x.day_index, x.sort_order))
    return itineraries


# create
@router.post("/{event_id}/create", response_model=ItineraryRead)
async def create_itinerary(
    event_id: str,
    payload: ItineraryCreate,
    member: EventMember = Depends(get_event_member),
    session: AsyncSession = Depends(get_session),
):
    itinerary = ItineraryItem(**payload.model_dump(), created_by=member.user_id, event_id=event_id)
    
    try:
        session.add(itinerary)
        await session.flush()

        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to create itinerary")
    
    await session.refresh(itinerary)
    return itinerary

# bulk reorder (can be updated by organizer and guest)
# accepts ordered list of IDs
@router.patch("/{event_id}/reorder", response_model=list[ItineraryRead])
async def bulk_reorder_itineraries(
    event_id: str,
    payload: list[ItineraryUpdateOrder],
    member: EventMember = Depends(get_event_member),
    session: AsyncSession = Depends(get_session),
):
    ids = [item.itinerary_id for item in payload]
    result = await session.execute(
        select(ItineraryItem).where(ItineraryItem.id.in_(ids))
    )
    itineraries_by_id = {itinerary.id: itinerary for itinerary in result.scalars().all()}

    # validate the whole batch before mutating anything, so a bad id in the
    # payload can't leave some items reordered and others untouched
    for item in payload:
        itinerary = itineraries_by_id.get(item.itinerary_id)
        if itinerary is None or str(itinerary.event_id) != event_id:
            raise HTTPException(status_code=404, detail="Itinerary not found")

    for item in payload:
        itineraries_by_id[item.itinerary_id].sort_order = item.sort_order

    result = [
        ItineraryRead.model_validate(itineraries_by_id[item.itinerary_id])
        for item in payload
    ]
    await session.commit()
    return result


# update (can be updated by organizer or guest)
@router.patch("/{event_id}/{itinerary_id}", response_model=ItineraryRead)
async def update_itinerary(
    event_id: str,
    itinerary_id: str,
    payload: ItineraryUpdate,
    member: EventMember = Depends(get_event_member),
    session: AsyncSession = Depends(get_session),
):
    itinerary = await session.get(ItineraryItem, itinerary_id)
    if itinerary is None or str(itinerary.event_id) != event_id:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(itinerary, field, value)
    itinerary.last_updated_by = member.user_id
    itinerary.last_updated_at = datetime.now(timezone.utc)
    session.add(itinerary)
    await session.commit()
    await session.refresh(itinerary)
    return itinerary


# delete (can be deleted by organizer)
@router.delete("/{event_id}/{itinerary_id}", response_model=ItineraryRead)
async def delete_itinerary(
    event_id: str,
    itinerary_id: str,
    member: EventMember = Depends(require_organizer),
    session: AsyncSession = Depends(get_session),
):
    itinerary = await session.get(ItineraryItem, itinerary_id)
    if itinerary is None or str(itinerary.event_id) != event_id:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    result = ItineraryRead.model_validate(itinerary)
    await session.delete(itinerary)
    await session.commit()
    return result