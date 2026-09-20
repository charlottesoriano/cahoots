# Lessons — Phase 3, `routers/itinerary.py`, `schemas/itineraries.py` & migrations

Notes from building out the itinerary CRUD + bulk reorder endpoints — covers questions asked and concepts clarified along the way, not the feature work itself (see [`plan/phase-3/README.md`](../plan/phase-3/README.md) for what was built and the checklist). Some of these build directly on [`phase-2-events-router.md`](phase-2-events-router.md) — referenced inline rather than repeated.

---

## 1. Checking a Pydantic schema against its SQLModel table

When reviewing `schemas/itineraries.py` against `models/itinerary.py`, the checklist that actually matters:

- Every field name/type on the `*Create`/`*Update`/`*Read` schemas lines up with the model column.
- `*Create` omits server-assigned fields (`id`, `created_by`, `created_at`) — the client shouldn't be able to set who created a row or when.
- `*Update` makes every field optional, and **also excludes server-assigned fields** — including audit columns like `last_updated_by`/`last_updated_at` (see §3 below). If those are settable from the request body, a client can spoof who last edited a row.
- `*Read`'s `Config.from_attributes = True` matches the pattern from `EventRead`.

One thing that looked like a mismatch but wasn't: `created_by: str` on `ItineraryRead`, even though the model's own comment says `# uuid, FK → users.id`. `models/users.py` shows `User.id: str` — it's not a DB-generated UUID, it's the Clerk/Supabase Auth user id passed in at signup. The model's comment is stale/aspirational; the schema is correct.

---

## 2. Applying a model change to Supabase — the Alembic workflow

Adding columns to a SQLModel table (`last_updated_at`, `last_updated_by`) doesn't touch the actual Postgres schema by itself. The project uses Alembic (`backend/alembic.ini`, `backend/migrations/`), pointed at `settings.DATABASE_URL` via `migrations/env.py`. From `backend/`:

```bash
alembic revision --autogenerate -m "add last_updated_at and last_updated_by to itinerary_items"
```

then review the generated file in `migrations/versions/` before applying — autogenerate is a diff tool, not a guarantee. Two things worth checking on a generated migration specifically:

- A new `NOT NULL` column on a table that may already have rows needs either a `server_default` (so existing rows get a value) or to be nullable — otherwise the migration fails against a non-empty table.
- `sqlalchemy.url` is a **sync** driver URL (`postgresql://`, psycopg2), separate from the app's own async engine (`postgresql+asyncpg://`, built in `database/database.py`) — Alembic can't run DDL through the async driver.

Once the file looks right:

```bash
alembic upgrade head
```

---

## 3. Auto-populating "who/when" audit columns

Can `last_updated_at`/`last_updated_by` be set automatically from the request, the way `created_by=user.id` is set in `create_event`? Partially:

- `last_updated_at` **can** be fully automatic at the DB level — `onupdate=func.now()` on the column makes Postgres stamp it on every `UPDATE`, no app code needed.
- `last_updated_by` **can't** be automatic that way — the database has no concept of "who's making this HTTP request." Only the app layer knows that (via `get_current_user`/`get_event_member`). It has to be set explicitly in the route handler:
  ```python
  itinerary.last_updated_by = member.user_id
  itinerary.last_updated_at = datetime.now(timezone.utc)
  ```
  which means **every** update route needs to remember to set it — nothing enforces it structurally.

Is the pattern worth having at all? Yes, as long as the expectation is "who touched this last" — cheap and standard. The limitation: these two columns only capture the *most recent* editor, not a history. If "who changed what and when, going back" ever becomes a real requirement, that needs a separate audit/changelog table, not more columns on the row itself.

---

## 4. Does `Depends(get_event_member)` actually block non-members before the query runs?

Yes — FastAPI resolves all dependencies before the route body executes. `get_event_member` queries `EventMember` for `(event_id, user.id)` and raises `HTTPException(403)` if no row exists; only if that doesn't raise does the route body run at all. So a non-member's request never reaches the `select(ItineraryItem)...` call — same mechanism as §9 in the phase-2 lessons file, just confirmed against a new route (`get_itineraries_for_event`).

---

## 5. When a dependency's parameter has no matching path placeholder

This is what caused a real authorization bug, and it's an extension of §7 in the phase-2 lessons file ("how FastAPI decides where a parameter comes from").

`get_event_member(event_id: str, ...)` has no `Depends(...)` default on `event_id`, so FastAPI looks for a `{event_id}` placeholder in the *route's* path to bind it to. Early draft of `create_itinerary` was `@router.post("/create", ...)` — no `{event_id}` in the path at all. FastAPI's fallback (rule 4 from §7): treat it as a **required query parameter** instead — `POST /itinerary/create?event_id=...`.

The bug: `ItineraryCreate` *also* had its own `event_id` field in the JSON body. Nothing checked that the query-string `event_id` (checked for membership) and the body's `event_id` (actually written to the new row) were the same value. A member of Event A could pass `?event_id=<event A>` to pass the membership check, while the body's `event_id` pointed at Event B — creating a row in an event they had no access to.

Fix: put `event_id` in the path (`@router.post("/{event_id}/create", ...)`), drop `event_id` from `ItineraryCreate` entirely, and build the row from the path value:
```python
itinerary = ItineraryItem(**payload.model_dump(), created_by=member.user_id, event_id=event_id)
```
Now there's no field left for a client to disagree with the verified value. The same shape of bug showed up again in `update_itinerary`/`delete_itinerary` — there, `session.get(ItineraryItem, itinerary_id)` fetched a row by PK alone with no check that it belonged to the `event_id` in the path. Fix there was an explicit check: `if itinerary is None or str(itinerary.event_id) != event_id: raise HTTPException(404)`.

---

## 6. Static path segments must be registered before dynamic ones

`PUT /{event_id}/reorder` and `PUT /{event_id}/{itinerary_id}` overlap — Starlette matches routes **in registration order**, and `{itinerary_id}` is just a string segment that will happily match the literal `"reorder"`. If the `{itinerary_id}` route is declared first in the file, a request to `.../reorder` gets swallowed by it (`itinerary_id="reorder"`, likely a 404 from a failed lookup) and the actual reorder handler never runs. Fix is ordering, not logic: literal/static paths need to come before parameterized ones at the same position. (Extends the route-order note in §3 of the phase-2 lessons file.)

---

## 7. Why returning an object right after `session.delete()` + `commit()` can crash

```python
await session.delete(itinerary)
await session.commit()
return itinerary   # boom
```

SQLAlchemy sessions default to `expire_on_commit=True` — after `commit()`, every attribute on `itinerary` is marked expired. When FastAPI serializes the return value against `response_model=ItineraryRead`, it reads those attributes, which triggers SQLAlchemy to try to refresh the object from the DB to get fresh values. But the row is gone — you just deleted it — so instead of a value, you get `sqlalchemy.orm.exc.ObjectDeletedError`. The delete itself succeeds; the response building is what blows up.

Fix: snapshot the data into the Pydantic model **before** deleting:
```python
result = ItineraryRead.model_validate(itinerary)
await session.delete(itinerary)
await session.commit()
return result
```
This is now the pattern in both `delete_itinerary` and `delete_event`.

---

## 8. Storing timestamps in UTC

`DateTime(timezone=True)` maps to Postgres `timestamptz`, which always stores internally as UTC — but it needs a **timezone-aware** Python `datetime` to know what offset to convert *from*. `datetime.now()` is naive (no offset info); `datetime.now(timezone.utc)` is aware. Passing the naive version to an aware column is what causes drivers to either error or silently guess wrong. On the way out, the API returns an aware UTC timestamp (e.g. `2026-09-20T14:32:10+00:00`); converting to the viewer's local timezone is a client-side concern (frontend), not something the backend needs to do.

---

## 9. Can a partial failure in a bulk operation leave some rows updated and others not?

Asked in the context of `bulk_reorder_itineraries` looping over a payload of `(itinerary_id, sort_order)` pairs. Original version validated and mutated one item at a time inside the same loop, then committed once after the loop:

```python
for item in payload:
    itinerary = await session.get(ItineraryItem, item.itinerary_id)
    if itinerary is None or str(itinerary.event_id) != event_id:
        raise HTTPException(status_code=404, ...)   # raised mid-loop
    itinerary.sort_order = item.sort_order
await session.commit()
```

Because `commit()` only happens once, after the whole loop finishes, a `raise` partway through means `commit()` never runs — nothing is persisted, even though SQLAlchemy's autoflush may have already *sent* some `UPDATE`s to Postgres within the still-open transaction (sent isn't committed; the transaction rolls back when the session closes without a commit). So it was already atomic, just implicitly.

Made it explicit instead, by validating the entire batch up front (one query, `WHERE id IN (...)`) before mutating anything, so a bad id can't even begin to touch other rows' state:
```python
result = await session.execute(select(ItineraryItem).where(ItineraryItem.id.in_(ids)))
itineraries_by_id = {i.id: i for i in result.scalars().all()}

for item in payload:                      # validate first
    itinerary = itineraries_by_id.get(item.itinerary_id)
    if itinerary is None or str(itinerary.event_id) != event_id:
        raise HTTPException(status_code=404, ...)

for item in payload:                      # only mutate after validation passes
    itineraries_by_id[item.itinerary_id].sort_order = item.sort_order

await session.commit()
```
Also worth noting: building the response list by iterating the dict (`itineraries_by_id.values()`) rather than the original `payload` would return items in the database's arbitrary query order instead of the order the client sent them in — easy to get wrong when refactoring a loop into a dict lookup.

---

## 10. Adding a `NOT NULL` column to a table that already has rows

Running the autogenerated migration for `last_updated_by`/`last_updated_at` against Supabase failed:

```
sqlalchemy.exc.IntegrityError: (psycopg2.errors.NotNullViolation) column "last_updated_by" of relation "events" contains null values
[SQL: ALTER TABLE events ADD COLUMN last_updated_by VARCHAR NOT NULL]
```

`last_updated_at` had a `server_default=sa.text('now()')`, so existing rows got backfilled automatically. `last_updated_by` had no default at all — Postgres tries to write `NULL` into a `NOT NULL` column for every pre-existing row and rejects the whole statement.

Two valid fixes, depending on whether the column is *conceptually* optional:

- **Backfill, then tighten** (used first, when `last_updated_by` was still meant to be required): add the column nullable, run an `UPDATE` to fill existing rows with a sensible value, then `alter_column(..., nullable=False)`. Here the sensible backfill was `last_updated_by = created_by` (the creator is the closest thing to a "last editor" a never-edited row has).
  ```python
  op.add_column('events', sa.Column('last_updated_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
  op.execute('UPDATE events SET last_updated_by = created_by WHERE last_updated_by IS NULL')
  op.alter_column('events', 'last_updated_by', nullable=False)
  ```
- **Just make it nullable** (what actually got used): if "no one has updated this yet" is a legitimate, permanent state — not just a migration-time gap — skip the backfill and `alter_column` step entirely; add the column as `nullable=True` and leave it. Simpler, and matches the real-world meaning better here: a row genuinely has no "last editor" until its first edit.

One rolled cleanly: since the whole migration runs inside a single transaction (`migrations/env.py` wraps `run_migrations()` in `context.begin_transaction()`), the failed statement rolled back everything else in that revision too — nothing was left half-applied, so it was safe to just edit the migration file in place and rerun, instead of writing a new one.

---

## 11. A Python-level `default=None` on a SQLModel field silently defeats `server_default`

While making `last_updated_by` nullable, `last_updated_at` got changed the same way by mistake:

```python
last_updated_at: datetime | None = Field(
    default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
)
```

This looks harmless — nullable, no big deal — but it would have broken every `create_itinerary`/`create_event` call once applied. The reason: `server_default` only takes effect when a column is **left out of the INSERT statement entirely**. `Field(default=None, ...)` gives every `ItineraryItem`/`Event` instance an explicit Python attribute value of `None` the moment it's constructed — from SQLAlchemy's point of view, the attribute *is* set (to `None`), not unset. So it sends `last_updated_at = NULL` explicitly, which never gives `server_default=func.now()` a chance to run, and would violate the column's `NOT NULL` constraint (which was correctly left in place, since a row's creation time genuinely should count as its first "last updated" timestamp).

The tell, in hindsight: `created_at` never had a `default=` kwarg on the `Field(...)` — only `sa_column=Column(..., server_default=func.now(), nullable=False)`. That absence is deliberate, not an oversight — it's what keeps the attribute "unset" at the Python level so the database's default actually gets used. Any column meant to auto-populate via `server_default` needs to follow that same shape; adding `default=` (even `default=None`) breaks it.

Fix was reverting `last_updated_at` to that original shape — no `default=`, `nullable=False`, `server_default=func.now()` — while leaving `last_updated_by` genuinely nullable, since only one of the two columns actually needed to change.

---

## 12. Dead client-settable fields are still a latent risk, even if unused

While fixing the above, `ItineraryUpdateOrder` (the bulk-reorder request schema) turned out to have picked up `last_updated_by`/`last_updated_at` as optional fields — but `bulk_reorder_itineraries` never actually read them; it only ever used `item.sort_order`. Not an active bug (nothing was being spoofed), but the same shape of problem flagged back in §1/§3 for `ItineraryUpdate`: a schema field a client can set, sitting unused, is one accidental `**item.model_dump()` or copy-pasted `setattr` loop away from becoming exploitable. Fix was just deleting the two fields from the schema — if reorder should someday also stamp who/when, that value should come from `member.user_id`/`datetime.now(timezone.utc)` in the route, the same way `update_itinerary` does it, never from the request body.
