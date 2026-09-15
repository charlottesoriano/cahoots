import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from core.config import settings
from database.database import get_session
from models.users import User

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Verifies the signature for one specific Clerk endpoint. Built once at import
# time — same reasoning as jwks_client in core/security.py: the secret doesn't
# change per request, so there's no reason to re-instantiate it every call.
webhook = Webhook(settings.CLERK_WEBHOOK_SIGNING_SECRET)


@router.post("/clerk")
async def clerk_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    # Signature verification needs the exact raw bytes Clerk signed — not a
    # re-serialized Pydantic model, which could differ byte-for-byte and fail
    # verification even for a genuine request.
    payload = await request.body()

    try:
        # .verify() checks svix-id/svix-timestamp/svix-signature against the
        # payload and secret, raises on mismatch. This installed svix version
        # (2.5.0) returns None on success — it doesn't hand back the parsed
        # body — so we decode it ourselves below once verification passes.
        webhook.verify(payload, dict(request.headers))
    except WebhookVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = json.loads(payload)

    if event.get("type") == "user.created":
        await _handle_user_created(event["data"], session)

    # Clerk/Svix retries on any non-2xx, so always return 200 once verified,
    # even if the event type is one we don't act on.
    return {"status": "ok"}


async def _handle_user_created(data: dict, session: AsyncSession) -> None:
    clerk_id = data["id"]

    # Svix guarantees at-least-once delivery, so the same event can arrive
    # more than once. Treat this as idempotent: if the row already exists,
    # there's nothing to do.
    if await session.get(User, clerk_id):
        return

    primary_email_id = data.get("primary_email_address_id")
    email_addresses = data.get("email_addresses", [])
    # next -> JS: find() ; flutter: firstWhereOrNull()
    primary_email = next(
        (e["email_address"] for e in email_addresses if e["id"] == primary_email_id),
        None,
    )
    # if primary_email is None, then email_addresses is not empty, we can use the first email address
    if primary_email is None and email_addresses:
        primary_email = email_addresses[0]["email_address"]

    if primary_email is None:
        # Nothing usable to store — ack anyway so Clerk stops retrying;
        # this is a data problem, not a transient failure.
        return

    display_name = " ".join(
        filter(None, [data.get("first_name"), data.get("last_name")])
    ).strip() or data.get("username") or primary_email

    session.add(
        User(
            id=clerk_id,
            email=primary_email,
            display_name=display_name,
            avatar_url=data.get("image_url"),
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        # Two deliveries raced past the .get() check above; the row exists now.
        await session.rollback()
