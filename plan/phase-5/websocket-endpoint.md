# Phase 5 · Item 1 — WebSocket endpoint

**Goal:** an authenticated WebSocket endpoint at `/ws/events/{event_id}` that only
members of the event can stay connected to.

**Decision:** FastAPI WebSocket endpoint instead of Supabase Realtime (learning
project; keeps auth in FastAPI/Clerk; Redis already available for later). No new
dependency — `uvicorn[standard]` already ships the `websockets` library.

> Steps 5–6 (connection manager) aren't built yet — they're picked up in item 2
> (broadcasting), since the manager only matters once something broadcasts.

---

## Background: the handshake and `accept()`

- A WebSocket connection starts life as a normal HTTP request saying "please
  upgrade me to a WebSocket" (the *handshake*).
- `await websocket.accept()` is a method on the `websocket` object the route
  receives. It says "yes" to the handshake — from then on the socket is open and
  both sides can send messages.
- Calling `websocket.close()` *before* `accept()` = saying "no" to the handshake.
  Starlette answers with HTTP 403, and the client only sees "connection failed"
  (no code, no reason).
- Calling `websocket.close(code=1008, reason="...")` *after* `accept()` sends a
  real close frame — the client can read the code and reason. (`1008` = "policy
  violation", the standard code for auth failures.)
- With first-message auth you **must** `accept()` first anyway: you can't read a
  message from a socket you haven't opened.

## 1. Router: `routers/websockets.py`

- Its own router — not `webhooks.py` (that's for incoming Clerk HTTP POSTs, unrelated).
- `APIRouter(prefix="/ws", tags=["websockets"])` + `@router.websocket("/events/{event_id}")`.
- Register in `main.py`: add `websockets` to the `from routers import ...` line and
  `app.include_router(websockets.router, prefix=settings.API_PREFIX)`.
  Full path: `{API_PREFIX}/ws/events/{event_id}` → `/api/v1/ws/events/{event_id}`.
- **Everything below happens inside the one route function** (`websocket_endpoint`)
  — no extra routers or endpoints.

## 2. Auth via first message

- Browsers can't set an `Authorization` header on a WebSocket, so the client
  authenticates in its first message: `{"type": "auth", "token": "<clerk_jwt>"}`.
- *Receive:* `websocket.receive_json()` (not `receive_text()`) — parses the JSON
  for you; raises `ValueError` if it isn't valid JSON.
- *Wrap:* put that call inside `asyncio.wait_for(..., timeout=5)` — raises
  `TimeoutError` if nothing arrives in 5s, so a client can't connect, stay silent,
  and hold the socket open forever.
- *Validate:* the parsed message is a `dict`, `message["type"] == "auth"`, and
  `message["token"]` is a `str`.
- Any failure → `await websocket.close(code=1008, reason=...)` then `return`.

## 3. Verify the token + check membership — differences from HTTP routes

- `get_current_claims` depends on `HTTPBearer`, which reads an HTTP `Request` —
  doesn't exist here. Call `verify_token(token)` from `core/security.py` directly.
- `verify_token` raises `HTTPException` — meaningless on a socket, so catch it and
  close with `1008`.
- Membership: `session.get(User, claims["sub"])` (`sub` is the PK) then
  `is_member(event_id, user, session)` from `services/event_members.py`.
- **DB session trap:** don't use `Depends(get_session)` — it keeps the session
  (and a pool connection) open for the socket's whole lifetime (could be hours).
  Open a short-lived `async with AsyncSession(engine) as session:` just for this
  check; it closes as soon as the block ends, before the receive loop.

### How the membership block works

```python
async with AsyncSession(engine) as session:
    user = await session.get(User, claims["sub"])
    allowed = user is not None and await is_member(event_id, user, session)
if not allowed:
    ...
```

- `async with` is a **statement** (like `if` / `for` / `try`), not a function. It
  opens the session, runs the block, and *always* closes it afterwards — even on
  error. Roughly equivalent to `session = AsyncSession(engine)` + `try: ... finally: close`.
- `allowed` is usable after the block because **only functions, classes, and
  modules create a new scope in Python** — `with` / `if` / `for` / `try` blocks
  don't. The indentation marks how long the session is open, not where variables live.
- `and` short-circuits: if `user is None`, `is_member` is never called (it would
  crash on `user.id`).

## 4. The full route (before the manager exists)

```python
@router.websocket("/events/{event_id}")
async def websocket_endpoint(websocket: WebSocket, event_id: uuid.UUID):
    # 1. finish the handshake — connection is open from here
    await websocket.accept()

    # 2. wait (max 5s) for the first message
    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
    except TimeoutError:
        await websocket.close(code=1008, reason="Auth timeout")
        return
    except ValueError:  # not valid JSON
        await websocket.close(code=1008, reason="Invalid message")
        return
    except WebSocketDisconnect:
        return  # client already left — nothing to close

    # 3. check the message's shape
    if (
        not isinstance(message, dict)
        or message.get("type") != "auth"
        or not isinstance(message.get("token"), str)
    ):
        await websocket.close(code=1008, reason="Expected auth message")
        return

    # 4. verify the Clerk token
    try:
        claims = verify_token(message["token"])
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid token")
        return

    # 5. membership check — session opens and closes right here
    async with AsyncSession(engine) as session:
        user = await session.get(User, claims["sub"])
        allowed = user is not None and await is_member(event_id, user, session)
    if not allowed:
        await websocket.close(code=1008, reason="Not authorized")
        return

    # 6. authenticated — keep the connection alive
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")  # echo, testing only
    except WebSocketDisconnect:
        pass  # client is already gone — do NOT call websocket.close() here
```

- Every failure path is `close` + `return`, so reaching step 6 means every check passed.
- Don't call `websocket.close()` after `WebSocketDisconnect` — the socket is
  already closed; Starlette raises `RuntimeError`.
- Keep close `reason`s short and generic: the WebSocket protocol caps them at 123
  bytes, and raw exception text can leak internals.

## 5. Connection manager (the room registry) — *done in item 2*

- Why: each connection only knows its own `websocket`. To broadcast "event X
  changed", something has to know *every* socket connected to event X.
- New module, e.g. `core/realtime.py`:

  ```python
  class ConnectionManager:
      def __init__(self):
          self.rooms: dict[uuid.UUID, set[WebSocket]] = {}

      def connect(self, event_id, websocket): ...      # add socket to rooms[event_id]
      def disconnect(self, event_id, websocket): ...   # remove it; drop the key if the set is empty
      async def broadcast(self, event_id, message: dict): ...  # send_json to each socket in the room

  manager = ConnectionManager()  # ONE shared instance for the whole app
  ```

- Everything imports that same object (`from core.realtime import manager`) — the
  route registers sockets, the itinerary service (item 2) broadcasts, and both see
  the same rooms.
- `broadcast`: iterate over a **copy** of the set (sockets can disconnect
  mid-loop); try/except each `send_json` so one dead socket doesn't break the rest.
- This is the in-memory registry that item 3 refers to.

## 6. Wire the manager into the route — *done in item 2*

- Add `manager.connect(event_id, websocket)` right before step 6's `try`.
- Add `finally: manager.disconnect(event_id, websocket)` after the `except` —
  runs however the loop ends, so closed sockets don't linger in the room.
- Because `connect` comes after all the early `return`s, the `finally` only ever
  runs for a socket that was actually registered.
- Remove the echo `send_text` once the connection is confirmed working.

## 7. Manual testing

- WebSocket routes **don't appear in Swagger UI** (`/docs`) — OpenAPI only
  describes HTTP request/response endpoints. The route still works; test it with
  Postman or the CLI instead.
- `event_id` must be a real event **UUID** (not `1`, `2`, …) — a non-UUID fails
  path validation before `accept()`, so the client sees `HTTP 403` instead of a
  `1008` close.
- Use a token from the same Clerk user who is a member of the event. Clerk session
  tokens only live 60s — for testing, create a JWT template (Dashboard → Configure
  → JWT templates, e.g. `dev-testing`, lifetime `3600`) and get a token in the
  app's browser console with
  `await window.Clerk.session.getToken({ template: "dev-testing" })`.
  Dev only — never use the long-lived template in the real app.

### Postman (recommended — you can type the message before connecting)

1. **New → WebSocket** (not HTTP).
2. URL: `ws://localhost:8000/api/v1/ws/events/<event_uuid>`
3. Message box: `{"type": "auth", "token": "<jwt>"}` (the `Text` format is fine —
   `receive_json()` parses it; `JSON` only adds highlighting).
4. Click **Connect**, then **Send** within 5 seconds. **Connect only opens the
   socket — it does not send the message.**
5. Read the result in the **Response** pane:
   - Still **Connected** after sending auth → success. Send `hello` → expect
     `Message received: hello`.
   - **Disconnected** → expand the row (⌄) to see the close code and reason.
6. **Disconnect** → **Connect** → **Send** again for each case below.

### CLI (alternative — interactive, timing is tight)

`uv run python -m websockets "ws://localhost:8000/api/v1/ws/events/<event_uuid>"`
— takes only the URI. After `Connected`, paste the auth JSON at the `>` prompt within 5s.

### Cases

| Send                                   | Expected                                             |
| -------------------------------------- | ---------------------------------------------------- |
| nothing, wait 5s                       | `1008 Auth timeout`                                  |
| `{"type": "nope"}`                     | `1008 Expected auth message`                         |
| `{"type": "auth", "token": "garbage"}` | `1008 Invalid token`                                 |
| valid token + `[no member]` event UUID | `1008 Not authorized`                                |
| valid token + member event UUID        | stays connected; `hello` → `Message received: hello` |

### Seed data (Supabase SQL Editor)

- `events.id` / `event_members.id` have no DB default (UUIDs are generated in
  Python), so seeds must use `gen_random_uuid()`.
- `role` needs a cast: `'organizer'::eventrole`.
- An event without an `event_members` row always closes with `Not authorized`.

### pytest

`TestClient(app).websocket_connect(...)` + `send_json(...)`.

## Gotchas

- CORS middleware doesn't apply to WebSockets. Origin check (optional): read
  `websocket.headers["origin"]` manually.
- Clerk tokens are short-lived (~60s), but auth is only checked on connect — a
  long-lived socket outliving its token is normal.
- The in-memory registry only works with a single uvicorn worker; Redis pub/sub
  fixes that (item 3).
