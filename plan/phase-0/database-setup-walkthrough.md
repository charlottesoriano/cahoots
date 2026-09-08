# Database Setup Walkthrough — Cahoots (Phase 0)

How the schema in [`database-schema.md`](./database-schema.md) got turned into real
tables in Supabase, written up from the working session on 2026-09-07.

Companion docs in this folder:
- [`database-schema.md`](./database-schema.md) — the table definitions (source of truth)
- [`alembic-setup.md`](./alembic-setup.md) — one-time Alembic wiring (env.py, alembic.ini, script.py.mako)

---

## Q: Do I create tables on the Supabase website, or from the FastAPI backend?

**From the backend.** Supabase just hosts Postgres and hands you a connection
string. Anything the Supabase SQL editor can do, Alembic can do over that same
connection string. So the flow is:

```
SQLModel model classes  ->  alembic revision --autogenerate  ->  alembic upgrade head
   (backend/models/)          (generates a migration file)        (runs CREATE TABLE on Supabase)
```

The Supabase dashboard is only needed later for things Alembic does not manage:
- **Row Level Security policies** (Phase 9)
- **Storage buckets** (cover images, avatars)
- **Auth** configuration (Clerk / Supabase Auth)

Table creation is 100% code.

---

## Step 1 — Write model files, one per domain

Files live in `backend/models/`, roughly one file per table (or per small group of
related tables). Build them **in phase order** — `users` -> `events` /
`event_members` -> `itinerary` -> `expenses` -> `polls` — so each phase only
depends on tables that already exist.

### model class vs table name

They are two separate things:

| | Name | Convention |
|---|---|---|
| Python class | `User` | PascalCase, singular |
| Postgres table | `users` | snake_case, plural — matches `database-schema.md` |

One model class maps to one table, but you spell the table name yourself with
`__tablename__`. SQLModel's auto-derived name would be `user` (lowercased class
name), **not** `users`, so always set `__tablename__` explicitly.

### Example: `backend/models/user.py`

Reference — the `users` table:

| Column | Type | Notes |
|---|---|---|
| id | uuid, PK | matches Clerk/Supabase Auth user id |
| email | text, unique | |
| display_name | text | |
| avatar_url | text, nullable | |
| push_token | text, nullable | Expo push token |
| created_at | timestamptz | default now() |

```python
import uuid
from datetime import datetime

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func


class User(SQLModel, table=True):
    __tablename__ = "users"

    # uuid, PK — "matches Clerk/Supabase Auth user id".
    # No default_factory: the id comes FROM Clerk/Supabase Auth, you pass it in
    # when creating the row (signup sync webhook, Phase 1).
    id: uuid.UUID = Field(primary_key=True)

    # text, unique
    email: str = Field(unique=True, index=True)

    # text, NOT NULL
    display_name: str

    # text, nullable
    avatar_url: str | None = Field(default=None)

    # text, nullable — Expo push token
    push_token: str | None = Field(default=None)

    # timestamptz, default now() — filled by Postgres, not Python
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
```

### Mapping rules (schema -> SQLModel)

| Schema says | Code | Why |
|---|---|---|
| `uuid, PK` | `Field(primary_key=True)` with type `uuid.UUID` | PK implies NOT NULL |
| id your app generates | add `default_factory=uuid.uuid4` | true for every table *except* `users` |
| id from an external system | no `default_factory` | `users.id` comes from Clerk/Supabase Auth |
| `text, unique` | `Field(unique=True)` (add `index=True` if looked up often) | |
| `text` (no "nullable") | non-optional type `str` | -> `NOT NULL` |
| `text, nullable` | `str \| None = Field(default=None)` | |
| `timestamptz default now()` | `sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)` | `server_default` puts `DEFAULT now()` in the DDL so the DB fills it; `timezone=True` -> `timestamptz` |
| `FK -> users.id` | `Field(foreign_key="users.id")` | |
| `enum('a','b')` | `enum.Enum` subclass + `sa_column=Column(SAEnum(MyEnum, name="my_enum"))` | native Postgres enum type |
| unique on `(a, b)` | `__table_args__ = (UniqueConstraint("a", "b"),)` | composite constraint |
| `numeric(10,2)` | `sa_column=Column(Numeric(10, 2))` | exact decimal, not float |

### `sa_column` — the escape hatch

Use a plain `Field(...)` when it can express what you need (unique, nullable,
foreign_key, primary_key, simple default). Drop to `sa_column=Column(...)` for
Postgres-specific behavior: `server_default`, `timestamptz`, `Numeric(p,s)`,
native enums. You can't mix `sa_column` with other DB-level `Field` args on the
same field — `sa_column` must then carry everything (`nullable=`, `unique=`, ...).

---

## Step 2 — Register models so Alembic sees them

Autogenerate only detects models imported **before** it reads
`SQLModel.metadata`. `migrations/env.py` does `import models`, so make
`backend/models/__init__.py` re-export each model:

```python
from models.user import User
from models.event import Event, EventMember, MemberRole
# ... add a line per model file

__all__ = ["User", "Event", "EventMember", "MemberRole"]
```

Add to this file every time you add a model module, or autogenerate will silently
miss the new table.

---

## Step 3 — Generate the migration

```powershell
cd backend
uv run alembic revision --autogenerate -m "initial schema"
```

### Error hit this session: "Target database is not up to date"

```
ERROR [alembic.util.messaging] Target database is not up to date.
FAILED: Target database is not up to date.
```

**Cause:** Alembic refuses to autogenerate while the database is behind the latest
migration file on disk. There was an earlier empty `initial_schema` migration
(generated when there were zero models, `upgrade()` was just `pass`) that had
never been applied. So `head` (on disk) != `current` (what `alembic_version` in
the DB says).

**Diagnose:**

```powershell
uv run alembic current   # what the DB is at (was blank)
uv run alembic heads     # latest file on disk
uv run alembic history   # the chain
```

**Fix used — delete the empty stub, since it did nothing:**

```powershell
Remove-Item migrations\versions\<timestamp>_..._initial_schema.py
Remove-Item migrations\versions\__pycache__\<same>.pyc   # if present
uv run alembic revision --autogenerate -m "initial schema"   # now works; new file is the base
```

Alternative (keep the stub): `uv run alembic upgrade head` first to apply the
no-op, then autogenerate — the new migration chains off it.

**Rule going forward:** always `uv run alembic upgrade head` before generating the
next migration.

---

## Step 4 — Review, then apply

Open the generated file in `migrations/versions/` and check:
- tables created in FK-dependency order (`users` before `events` before `event_members`)
- enums: Alembic creates the type in `upgrade()` but often forgets to drop it in
  `downgrade()` — add the drop manually if clean rollbacks matter
- `server_default` present on `created_at`
- no spurious/unrelated changes

```powershell
uv run alembic upgrade head
```

Verify in Supabase -> Table Editor: your tables plus an `alembic_version` table.

---

## Step 5 — Housekeeping

- **Commit the migration files.** `backend/migrations/versions/*.py` are source,
  not build artifacts — they must be in git so the schema is reproducible. Check
  `.gitignore` isn't excluding `migrations/versions/`.
- **`init_db()` is dead code.** `backend/database/database.py` defines `init_db()`
  (runs `SQLModel.metadata.create_all`) but nothing calls it — not `main.py`, no
  `lifespan`, no `on_event`. Once Alembic owns the schema, delete the function so
  no one wires it up later. Schema changes go through Alembic only.
- `uv run alembic current` should print the latest revision with `(head)`.

---

## The "UNRESTRICTED" badge in the Supabase Table Editor

Every table shows `UNRESTRICTED` = **Row Level Security is off**.

Deferring RLS to Phase 9 is the plan, but it is not harmless: Supabase exposes
every table over an auto-generated REST + realtime API reachable with the
**publishable / anon key**, which typically ships inside the React Native app.
With RLS off, anyone holding that key can read/write these tables directly,
bypassing FastAPI and its auth.

- **Local dev now:** fine, ignore it.
- **Before deploying anything real**, do one of:
  1. Enable RLS on every table with policies keyed on `event_members` (the
     Phase 9 approach), or
  2. Never ship the anon key to clients — all data access goes through FastAPI
     using the **secret** key only, leaving the anon API surface with no valid key.

---

## Day-to-day workflow (from `alembic-setup.md`)

| Action | Command |
|---|---|
| Made model changes, create migration | `uv run alembic revision --autogenerate -m "add events table"` |
| Apply pending migrations | `uv run alembic upgrade head` |
| Roll back one | `uv run alembic downgrade -1` |
| Current revision | `uv run alembic current` |
| History | `uv run alembic history` |
