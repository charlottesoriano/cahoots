# Lessons — Phase 2, `routers/events.py` & `core/permissions.py`

Notes from working through the Phase 2 event CRUD implementation — covers the FastAPI/Pydantic/SQLModel mechanics that came up along the way, not the feature work itself (see [`plan/phase-2/README.md`](../plan/phase-2/README.md) for what was built and the bugs hit).

---

## 1. Dictionary unpacking (`**`) and `.model_dump()`

```python
event = Event(**payload.model_dump(), created_by=user.id)
```

- `payload` is the `EventCreate` object FastAPI built from the incoming JSON body.
- `.model_dump()` (Pydantic v2) converts it to a plain dict: `{"title": "...", "description": None, ...}` — one key per field defined on `EventCreate`.
- `**` is Python's dict-unpacking operator. `SomeClass(**some_dict)` expands the dict into keyword arguments, as if you'd written each key/value pair by hand: `Event(title="...", description=None, ...)`.
- `created_by=user.id` is added on top — deliberately **not** part of `EventCreate`, because letting a client set who "created" an event would be a security hole. It's set server-side from the authenticated user instead.

Written out longhand, without unpacking, it'd be the more verbose:

```python
event = Event(
    title=payload.title,
    description=payload.description,
    location=payload.location,
    start_date=payload.start_date,
    end_date=payload.end_date,
    cover_image_url=payload.cover_image_url,
    created_by=user.id,
)
```

Same result — `**model_dump()` just avoids re-listing every field name twice.

---

## 2. `try`/`except` around database writes

```python
try:
    session.add(event)
    await session.flush()
    session.add(EventMember(...))
    await session.commit()
except SQLAlchemyError:
    await session.rollback()
    raise HTTPException(status_code=500, detail="Failed to create event")
```

- `SQLAlchemyError` is the base class for essentially every exception SQLAlchemy/asyncpg can raise (constraint violations, dropped connections, timeouts) — one `except` catches any DB failure in the block instead of listing each exception type.
- `await session.rollback()` undoes the *whole* transaction if anything partway through fails — e.g. the `Event` insert succeeds but the `EventMember` insert doesn't. Without it you could end up with an event that has no organizer.
- Raising `HTTPException(500, ...)` turns a raw DB exception into a clean response instead of leaking a stack trace to the client.
- `await session.refresh(event)` is deliberately left **outside** the `try` — by that point `commit()` already succeeded, so the row exists; a failure there is a separate, unlikely problem, not a "failed to create."

---

## 3. FastAPI path parameters

```python
@router.get("/{event_id}", response_model=EventRead)
async def get_event(event_id: uuid.UUID, ...): ...
```

- `{event_id}` in the route decorator is the same idea as Express's `router.get('/:id', ...)` — curly braces instead of a colon.
- The function parameter `event_id` is matched **by name** against that placeholder.
- The type hint (`uuid.UUID`, `str`, etc.) makes FastAPI auto-validate and auto-convert the URL segment. A request to `/events/not-a-uuid` against a `uuid.UUID`-typed param gets rejected with `422` before the function body ever runs — no manual `req.params.id` parsing/validation needed, unlike Express.
- Route **order** matters when paths could collide — a static path like `/events/mine` needs to be declared *before* `/events/{event_id}`, or FastAPI tries to parse `"mine"` as the dynamic segment first.

---

## 4. Why separate `EventCreate` / `EventUpdate` / `EventRead` schemas

- **`EventCreate`** — the request body for `POST`. Only fields a client should be able to set. No `id`/`created_by`/`created_at` — those are server-assigned.
- **`EventUpdate`** — the request body for `PATCH`/`PUT`. Every field is **optional** (`= None` default), because a partial update means the client only sends what's changing. Reusing `EventCreate` here would force PUT-style semantics (resend everything) or require `exclude_unset` tricks on a schema that doesn't actually document itself as "all optional" in the generated OpenAPI docs.
- **`EventRead`** — the response body, built from the ORM object via `Config.from_attributes = True` (Pydantic v2's replacement for `orm_mode`). Includes server-set fields the client never sends (`id`, `created_by`, `created_at`).
- **`DELETE`** needs no schema at all — just the `event_id` path parameter.

---

## 5. `Depends()` and how FastAPI resolves dependency chains

`Depends(fn)` does **not** mean "call `fn()` right here in this line of code." It means "before this function can run, resolve `fn` the same way — recursively, if `fn` itself has dependencies — and use whatever it returns as this parameter's value." FastAPI builds the whole chain into a graph per request and resolves it bottom-up; you never write the actual calls yourself.

Full trace for a route with `user: User = Depends(get_current_user)`:

```python
def get_current_claims(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict: ...
async def get_current_user(claims: dict = Depends(get_current_claims), session: AsyncSession = Depends(get_session)) -> User: ...
```

1. FastAPI sees the route needs `get_current_user`.
2. To call it, it first needs `claims` → resolves `get_current_claims`.
3. To call *that*, it first needs `creds` → resolves `bearer_scheme(request)` (this one needs nothing but the raw `Request`, which FastAPI already has).
4. `bearer_scheme` returns `creds` (or `None`).
5. `get_current_claims(creds=...)` runs → returns the decoded claims dict.
6. `get_current_user(claims=..., session=...)` runs → returns the `User`.
7. Only now does the route function itself run, with `user` already populated.

**Dependency caching**: if the same dependency (e.g. `get_current_user`) is needed in more than one place for a single request — say, once at the router level (`dependencies=[Depends(get_current_user)]`, used just to gate access) and again at the route level (`user: User = Depends(get_current_user)`, used to actually get the value) — FastAPI only calls it **once** per request and reuses the cached result for every other place that asks for it.

---

## 6. `HTTPBearer` — what it actually does

```python
bearer_scheme = HTTPBearer(auto_error=False)
creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)
```

- `HTTPBearer` is a FastAPI *security scheme* — its whole job is reading the `Authorization` header, checking it's shaped like `Bearer <token>`, and handing back the pieces already split apart (`.scheme` = `"Bearer"`, `.credentials` = just the token string).
- It doesn't validate the token itself — it doesn't know or care whether it's expired, forged, or garbage. That's `verify_token()`'s job (signature + issuer check against Clerk's JWKS).
- `auto_error=False` changes its failure behavior: by default, a missing/malformed header makes `HTTPBearer` raise its own `403` immediately. With `auto_error=False`, it returns `None` instead, so the calling code can raise a more semantically correct `401` (with `WWW-Authenticate: Bearer`) itself.
- Because it's a recognized *security* class (not just a generic dependency), FastAPI also reflects it into the OpenAPI schema automatically — that's why `/docs` shows the padlock icon and a bearer-token field for these routes.

---

## 7. How FastAPI decides *where* a parameter comes from

For each parameter in a route or dependency function, in order:

1. **Default is `Depends(...)`** → sub-dependency (see §5).
2. **Name matches a `{placeholder}` in the route's path string** → path parameter, pulled from the URL segment.
3. **Type is a Pydantic/SQLModel `BaseModel`** (e.g. `payload: EventCreate`) → request body, parsed from JSON. No name-matching — the whole body is parsed against the schema.
4. **Everything else** (plain `str`/`int`/`bool`/etc., no path match) → query parameter, matched by name (`?event_id=...`).
5. **Headers/cookies are never auto-extracted by name** — only via explicit `Header(...)`/`Cookie(...)` defaults. The `Authorization` header specifically goes through the `HTTPBearer` mechanism (§6), not name-matching.

This applies identically inside nested dependencies, not just route functions directly — see §8.

---

## 8. `event_id` flowing through nested dependencies

```python
# core/permissions.py
async def get_event_member(
    event_id: str,                              # <- no Depends default
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EventMember: ...

async def require_organizer(
    member: EventMember = Depends(get_event_member),
) -> EventMember: ...

# routers/events.py
@router.delete("/{event_id}", response_model=EventRead)
async def delete_event(
    event_id: str,
    member: EventMember = Depends(require_organizer),
    session: AsyncSession = Depends(get_session),
): ...
```

`get_event_member`'s `event_id` has no `Depends(...)` default, so per rule 2 above it's a **path parameter** — resolved from the *same* incoming request's URL as the route's own `event_id`, no matter how deep in the dependency chain it's declared. FastAPI flattens the entire dependency graph for a route before resolving anything, so it doesn't matter that `get_event_member` is two levels removed from the actual route function.

**This is name-sensitive.** If `get_event_member` had instead declared `eventId: str` (case mismatch) while the route path stayed `/{event_id}`, FastAPI would find no matching `{placeholder}`, fall through to rule 4, and treat it as a **required query parameter** — `?eventId=...`. Since no client sends that, the request fails with `422 Unprocessable Entity` (`{"loc": ["query", "eventId"], "msg": "Field required"}`) before the function body ever runs. Not a silent bug, not a crash — a loud, immediate validation error, but one whose cause (a path/query naming mismatch) is only obvious once you know this mechanism.

---

## 9. Dependencies used purely for their side effects

```python
async def get_event_details(
    event_id: str,
    member: EventMember = Depends(get_event_member),   # never referenced below
    session: AsyncSession = Depends(get_session),
):
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
```

`member` is never read in the function body — and that's correct, not a bug. `get_event_member`'s real job happens as a **side effect**: it queries `event_members` for `(event_id, user.id)` and raises `HTTPException(403)` if no row exists. The route doesn't need `member`'s fields (role, joined_at); it only needs the dependency to have run and not thrown. The parameter still has to be named and typed because that's how you tell FastAPI "run this dependency here" — there's no "run but don't bind" syntax. (Some codebases underscore-prefix it — `_member: EventMember = Depends(...)` — as a convention signaling "intentionally unused.")

This is also why `require_organizer` exists as its own function layered on top of `get_event_member` rather than duplicating the membership query: `require_organizer(member: EventMember = Depends(get_event_member))` reuses the membership check (and its 403) via the same dependency-caching behavior from §5, then adds one more condition (`role == organizer`) on top.

---

## 10. Why `event_members` + role checks live in a *dependency*, not inline per-route

Authentication ("is this a valid logged-in user?") and authorization ("is *this* user allowed to touch *this* event, and at what level?") are different questions. The router-level `dependencies=[Depends(get_current_user)]` only answers the first one. Without a membership/role check, any authenticated user who merely knows or guesses an `event_id` could read, edit, or delete an event they were never invited to.

Putting `get_event_member`/`require_organizer` in `core/permissions.py` (not inline in each route, and not inside `routers/events.py` itself) matters because:

- **Consistency** — one hand-rolled inline check per route (as an early draft of this code had — `event.created_by != user.id` for delete, `event.members.any(...)` for detail) means every route can get the rule subtly wrong in a different way. One example that actually happened here: an inline check read `if event.members.any(user_id=user.id): raise 403` — inverted, blocking members and letting non-members through.
- **Reuse across future routers** — per the schema notes, every event-scoped table in later phases (itinerary, expenses, polls, packing) needs the same "does this user have a row in `event_members` for this `event_id`" check. A shared dependency in `core/` means every future router just does `from core.permissions import get_event_member, require_organizer`, the same way routers already do `from core.security import get_current_user`.
- **Uses the actual data model** — `EventMember.role` (organizer/guest) is what the table was built for. An inline `created_by == user.id` check ignores it entirely, and breaks the moment a second organizer exists (e.g. a promoted guest) who isn't the original creator.
