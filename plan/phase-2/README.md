# Phase 2 — Users & Events (core CRUD)

Goal: create/read/update/delete events, with membership + roles enforced.

## Checklist

- [x] `POST /events` — create event (title, dates, location, cover image)
- [x] `GET /events` — list events the current user belongs to
- [x] `GET /events/{event_id}` — event detail
- [x] `PATCH /events/{event_id}` — edit event (organizer only)
- [x] `DELETE /events/{event_id}` — delete event (organizer only)
- [x] `event_members` table + role enforcement (organizer/guest) via dependency/decorator

## Tables involved

`events`, `event_members` — see `[../phase-0/database-schema.md](../phase-0/database-schema.md)`.
`event_members` has a unique constraint on `(event_id, user_id)`.

## Session notes (2026-09-19) — event CRUD implementation

### What was built

- **`schemas/events.py`** — `EventCreate` (request body for create), `EventUpdate` (all fields optional, for partial edits), `EventRead` (response model, `from_attributes = True`).
- **`routers/events.py`** — full event CRUD:
  - `POST /events/create` — creates the `Event` row, then an `EventMember` row with `role=organizer` for the creator, in one transaction (`flush()` before the second insert so `event.id` is available, `commit()` once at the end).
  - `GET /events/all` — lists events the current user belongs to, via `select(Event).where(Event.members.any(user_id=user.id))`.
  - `GET /events/{event_id}` — event detail, gated by `Depends(get_event_member)` (any member can view).
  - `PUT /events/{event_id}` — partial edit via `payload.model_dump(exclude_unset=True)`, gated by `Depends(require_organizer)`.
  - `DELETE /events/{event_id}` — gated by `Depends(require_organizer)`.
- **`core/permissions.py`** (new) — reusable FastAPI dependencies instead of ad hoc per-route checks:
  - `get_event_member(event_id, user, session)` — looks up the `EventMember` row for `(event_id, user.id)`, raises `403` if none exists, otherwise returns it. This is what "membership" enforcement means in practice — every event-scoped route in later phases (itinerary, expenses, polls, packing) can reuse this the same way.
  - `require_organizer(member)` — builds on `get_event_member`, additionally raises `403` unless `member.role == EventRole.organizer`.

### Deviations from the checklist's literal wording

- Routes are `/events/create` and `/events/all` rather than bare `POST /events` / `GET /events` — explicit path segments, functionally equivalent.
- The edit endpoint is `PUT`, not `PATCH` — but behaves like a partial update (`exclude_unset=True` only applies fields the client actually sent), so it's PATCH semantics on a PUT verb.

### Bugs hit this session, and the fix

1. **`socket.gaierror: [Errno 11001] getaddrinfo failed`** on every DB-touching request.
   Supabase's *direct connection* host (`db.<ref>.supabase.co`) only has an IPv6 (AAAA) DNS record, no IPv4 (A) record, and this network couldn't route IPv6.
   *First attempt (wrong):* switched to the session pooler — Supabase's own dashboard confirmed session pooler is also IPv6-only.
   *Fix:* switched `DATABASE_URL` to the **transaction pooler** URI (port `6543`), which Supabase serves over IPv4.
   *Follow-up flagged but not yet applied:* `asyncpg` prepared statements can misbehave behind a transaction-mode pooler; `create_async_engine` may need `connect_args={"statement_cache_size": 0}` if `"prepared statement ... does not exist"` errors show up later.

2. **`'AsyncSession' object has no attribute 'exec'`**.
   `database.py` built its session from `sqlalchemy.ext.asyncio.AsyncSession` — the plain SQLAlchemy class, which has no `.exec()`. `.exec()` is a SQLModel-only convenience method.
   *Fix:* changed the import in `database/database.py` to `from sqlmodel.ext.asyncio.session import AsyncSession` (a drop-in subclass that adds `.exec()`), and updated the type hints in the routers to match.

3. **`fastapi.exceptions.ResponseValidationError`** — every field reported `'type': 'missing'`, and the logged `input` was a 1-tuple like `(Event(...),)` instead of a bare `Event`.
   Even after fixing bug #2, `routers/events.py` was building the query with `from sqlalchemy import select` instead of `from sqlmodel import select`. SQLModel's `.exec()` only auto-unwraps rows into bare model instances when the statement is SQLModel's own `SelectOfScalar` type (checked via `isinstance`); a plain SQLAlchemy `Select` falls through and returns raw `Row` tuples instead.
   *Fix:* changed the import to `from sqlmodel import select`. Rule of thumb for this codebase going forward: always `from sqlmodel import select`, never `sqlalchemy`'s.

4. **`pydantic_core.ValidationError` on startup** — `.env` had `REDIS_URL`, `ENVIRONMENT`, `CORS_ORIGINS` that `Settings` didn't declare (`extra_forbidden`).
   *Fix (done independently):* `core/config.py`'s `Settings` class was updated to declare `ENVIRONMENT` and `REDIS_URL`, and `ALLOWED_ORIGINS` was renamed to `CORS_ORIGINS` to match `.env` and `main.py`'s CORS middleware.

### Still open / worth doing next

- Apply the `statement_cache_size=0` connect arg to the async engine if transaction-pooler + prepared-statement errors show up.
- Drop the now-unused `from sqlalchemy.orm import selectinload` import in `routers/events.py` if nothing ends up using it.
- Decide whether to rename `PUT /events/{event_id}` to `PATCH` to match the checklist literally, or update the checklist wording instead.