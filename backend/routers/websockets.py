import asyncio
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from core.security import verify_token
from database.database import engine
from models.users import User
from services.event_members import is_member

router = APIRouter(prefix="/ws", tags=["websockets"])

@router.websocket("/events/{event_id}")
async def websocket_endpoint(websocket: WebSocket, event_id: uuid.UUID):
    await websocket.accept()
    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
    except TimeoutError: # auth timeout
        await websocket.close(code=1008, reason="Auth timeout")
        return
    except ValueError:  # invalid message
        await websocket.close(code=1008, reason="Invalid message")
        return
    except WebSocketDisconnect:
        return # client already left - nothing to disconnect

    # check the shape of the message
    if(
        not isinstance(message, dict) or
        message.get("type") != "auth" or
        not isinstance(message.get("token"), str)
    ):
        await websocket.close(code=1008, reason="Expected auth message")
        return


    # verify the token with clerk
    try:
        claims = verify_token(message["token"])
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return


    # membership check
    async with AsyncSession(engine) as session: # manages something that has to be opened and then reliably closed (like a db session)
        user = await session.get(User, claims["sub"])
        allowed = user is not None and await is_member(event_id, user,session)
    if not allowed:
        await websocket.close(code=1008, reason="Not authorized")
        return

    # keep the connection alive
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        return # client already left - nothing to disconnect
    