# Lessons — Phase 4, `routers/invites.py`, `services/invites.py` & `services/event_members.py`

Notes from building the invite-link flow: generating a link, accepting it, and joining an event as a guest. This covers the design questions and the bugs that came up in review, not the feature itself (see [`plan/phase-4/README.md`](../plan/phase-4/README.md) for the checklist). It builds on [`phase-2-events-router.md`](phase-2-events-router.md) and [`phase-3-itinerary-router.md`](phase-3-itinerary-router.md).

---

## ⚠️ 0. `session.get()` only works with the primary key. (This mistake happened twice.)

```python
await session.get(EventMember, event_id, user.id)   # ❌ wrong
```

`session.get(Model, key)` looks a row up by its **primary key only**. `EventMember`'s primary key is its own `id` column. It is **not** `(event_id, user_id)`. The third positional argument is `options`, not a second key, so this either raises an error or searches for a member whose `id` equals the event's ID (which never matches).

This mistake happened twice in this phase, first in `is_member` and then in `accept_invite`. The rule:

- **If you're looking up by `id`**, use `session.get(Model, id)`.
- **For anything else** (another column, several columns, a unique column like `token`), use a query:

```python
result = await session.exec(
    select(EventMember).where(EventMember.event_id == event_id, EventMember.user_id == user.id)
)
member = result.first()   # EventMember or None
```

---

## 1. Designing the expiry

The `expires_at` column is nullable, so nothing expires unless your own code sets and checks it. Options considered:

| Option | Problem |
|---|---|
| `expires_at = event.end_date` | `end_date` is a `date` but the column is `timestamptz`, and asyncpg rejects a bare `date`. A date also means midnight at the *start* of the day, cutting off the last day. The stored value goes stale if the event's dates are edited later. |
| `datetime.combine(end_date, time.max, tzinfo=utc)` | Fixes the type, but it's still stale after date edits and still `None` for events without dates. |
| **`now + timedelta(hours=24)`** ✅ | Every invite gets an expiry, and it doesn't depend on the event dates. |

The final design has two checks in `is_expired`:
1. a stored 24-hour limit (`invite.expires_at < now`);
2. a check against the event's **live** `end_date` (`event.end_date < now.date()`).

The effective expiry is whichever comes first, and editing the event's dates never leaves stale invite rows.

Trade-off: 24 hours is strict for a group chat. If people complain, 3–7 days is common. Consider moving it into config.

---

## 2. SQLModel vs SQLAlchemy: `exec()` vs `execute()`

### Which session you have

- `from sqlmodel.ext.asyncio.session import AsyncSession` is **SQLModel's** session. It adds `exec()` and marks `execute()` as deprecated, which is why the editor shows a strikethrough.
- `from sqlalchemy.ext.asyncio import AsyncSession` is **SQLAlchemy's** parent class. It has no warning, because `execute()` is its normal method.
- `database/database.py` always creates SQLModel's session. The annotation only changes what the editor displays.

### What each one returns

Both return a *result object*, never the rows themselves and never `None`. You still call `.first()`, `.all()` and so on. The difference is **what's inside** that result.

**`execute()` returns `Row` objects.** A `Row` is tuple-like, with one slot per thing in the `select`. Even `select(EventInvite)` gives rows that each hold a single `EventInvite`:

```python
result = await session.execute(select(EventInvite).where(EventInvite.token == token))
row = result.first()        # Row: (EventInvite(...),)  ← a 1-item tuple, not the model
row.expires_at              # ❌ AttributeError — the Row doesn't have model columns
row[0].expires_at           # ✅ works, but awkward
```

So with `execute()`, you add `.scalars()` to take the first slot of each row:

```python
result = await session.execute(select(EventInvite).where(...))
invite = result.scalars().first()    # EventInvite or None
invites = result.scalars().all()     # list[EventInvite]
```

**`exec()` with SQLModel's `select` returns the models directly** when you select a single model (or a single column). There's no `.scalars()` step:

```python
result = await session.exec(select(EventInvite).where(EventInvite.token == token))
invite = result.first()     # EventInvite or None
invites = result.all()      # list[EventInvite]
```

**Selecting several things gives tuples either way:**

```python
result = await session.exec(select(EventInvite.token, EventInvite.expires_at))
for token, expires_at in result.all():   # each item is a tuple
    ...
```

| | `execute()` | `exec()` + `sqlmodel.select` |
|---|---|---|
| `select(Model)` | rows of `(Model,)`, so you need `.scalars()` | `Model` objects directly |
| `select(Model.col)` | rows of `(value,)`, so you need `.scalars()` | the values directly |
| `select(A, B)` | rows of `(a, b)` | tuples of `(a, b)` |
| Editor type hints | `Row[Any]`, so no autocomplete | knows `.first()` is `EventInvite \| None` |

### The mixing bug

SQLModel's `exec()` decides whether to unwrap the rows based on **which `select` built the statement**. If you pass it **SQLAlchemy's** `select`, it treats it like `execute()` and gives you `Row`s. That's why `invite.expires_at` failed while `services/invites.py` imported `select` from `sqlalchemy`.

**Rule:** import `select` and `AsyncSession` from the same library, and in this project that's `sqlmodel`:

```python
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
```

(`routers/itinerary.py` still uses SQLAlchemy's `select` with `execute().scalars()`. That works because the pair is consistent, but it's the odd one out.)

## 3. Getting one row or none

| Method | 0 rows | 1 row | 2+ rows |
|---|---|---|---|
| `.first()` | `None` | the row | first row, the rest are ignored |
| `.one_or_none()` | `None` | the row | raises |
| `.one()` | raises | the row | raises |

- **`.first()` doesn't limit the SQL.** The database still returns every match and Python keeps the first. Add `.limit(1)` to push the limit into the query.
- **The SQL syntax differs.** Postgres writes it as `LIMIT 1`; `TOP 1` is SQL Server.
- **On a unique column** like `token`, the limit doesn't matter, because only one row can match.
- **Because `exec()` never returns `None`, `if result is None` is always false.** You have to call `.first()` or a similar method on it.

## 4. Datetimes

- **`timestamptz` columns come back timezone-aware.** Comparing them with a naive `datetime.now()` raises `TypeError`. Use `datetime.now(timezone.utc)`.
- **A `date` column can't be compared with a `datetime`.** Compare `event.end_date < now.date()`.

---

## 5. Error handling

```python
try:
    session.add(member)
    await session.commit()
except IntegrityError:            # must come BEFORE SQLAlchemyError (it's a subclass)
    await session.rollback()
    raise HTTPException(409, "Already a member of this event")
except SQLAlchemyError:
    await session.rollback()
    raise HTTPException(500, "Failed to add member to event")
```

### What `IntegrityError` is for

`IntegrityError` is what SQLAlchemy raises when **the database refuses a write because it would break one of the table's rules (constraints)**:

| Constraint | Example in this project |
|---|---|
| **Unique** | inserting a second `event_members` row for the same (`event_id`, `user_id`), or a duplicate `event_invites.token` |
| **Foreign key** | an `event_members.event_id` that points at an event that doesn't exist |
| **Not null** | leaving a required column empty |
| **Check** | a value outside a `CHECK (...)` rule, if any are added later |

Why catch it separately from `SQLAlchemyError`:

- **It tells you the *data* was the problem, not the server.** A duplicate or a missing parent row is usually caused by the request (a client-side problem, so a 4xx status), while other `SQLAlchemyError`s (lost connection, timeout, syntax error) are server-side problems, so a 500 fits.
- **It lets you give a meaningful status.** Here, a unique violation on `event_members` means "already a member", so the client gets **409 Conflict** instead of a generic 500.
- **The order matters.** The hierarchy is `IntegrityError` → `DatabaseError` → `DBAPIError` → `StatementError` → `SQLAlchemyError`. Python uses the first `except` that matches, so if `SQLAlchemyError` comes first it catches the `IntegrityError` too, and you get a 500.
- **The database is the only reliable guard against races.** Two simultaneous accepts can both pass the "already a member?" check in Python before either inserts. Only the unique constraint actually stops the duplicate, and `IntegrityError` is how you find out. Handling it is the real fix, not a workaround.
- **One `IntegrityError` can have several causes.** It's raised for *any* constraint, so if a route could violate more than one, look at `e.orig` (the underlying asyncpg error, which includes the constraint name) to tell them apart. In `add_member`, the accept route has already confirmed the event exists, so in practice it means a duplicate.

### Other rules

- **Don't use `detail=str(e)`.** It sends SQL, table and constraint names, and parameter values to the client. Return a generic message and log the details on the server.
- **Don't add an `except Exception` alongside.** It turns real bugs (such as `AttributeError` from a typo) into vague 500s.
- **Import the exception classes.** Python only evaluates an `except` clause when an error happens, so without the imports the happy path still works, but the first real error becomes a `NameError`.
- **`await session.rollback()`.** Without `await`, the rollback never runs.

## 6. HTTP status codes used

| Case | Code |
|---|---|
| Invite created | 201 |
| Malformed UUID in path | 422 (automatic, see §7) |
| Not an organizer, or event doesn't exist | 403 (`require_organizer`) |
| Token not found, or token/event mismatch | 404 |
| Invite expired or event ended | 410 Gone |
| Already a member (race) | 409 |
| Already a member (accepting again) | 200, returns the existing membership |

- **Never raise `HTTPException(status_code=200)`.** The client sees "success" with a `{"detail": ...}` body instead of a member.
- **Returning 403 for a missing event** is standard, because it doesn't reveal which event IDs exist.
- **A token/event mismatch returns the same 404 as a made-up token.** Matching the `event_id` is a sanity check against mangled links, not extra security. The token alone is the secret.

## 7. `uuid.UUID` path parameters

- **FastAPI supports `uuid.UUID` as a parameter type.** The URL text is parsed before your code runs, and invalid input gets a **422**. With `str`, a bad ID reaches Postgres and comes back as a **500**.
- **Type the dependency the same way as the route.** Both `get_event_member` in `core/permissions.py` and the route's own `event_id` should be `uuid.UUID`.
- **Once something is a UUID, don't convert it again.** `uuid.UUID(<UUID object>)` raises `AttributeError: 'UUID' object has no attribute 'replace'`. That broke every accept until `add_member` went back to taking a `uuid.UUID` directly.
- **Changing the type also changes how comparisons behave.** In `routers/itinerary.py`, `str(itinerary.event_id) != event_id` became **always true** once `event_id` was a UUID, because a `str` never equals a `UUID`. That quietly broke reorder, update and delete. Compare UUID to UUID: `itinerary.event_id != event_id`.

## 8. Permissions and trusting the client

- **The create-invite route must use `Depends(require_organizer)`.** Without it, any logged-in user could create an invite for someone else's event and then accept it themselves.
- **Don't take server-owned fields from the request body.** The original `EventInviteCreate` payload accepted `event_id`, `token` and `created_by`, which would have let a client choose its own token or pretend to be someone else. All three are set on the server: from the path, from `secrets`, and from `user.id`.
- **Get the direction of the membership check right.** The person creating an invite must *be* a member (an organizer). Checking "already a member → reject" on the create route would have blocked every organizer.
