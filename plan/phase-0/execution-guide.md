# Execution Guide — Docker primer + full backend build order

Working notes for finishing Phase 0 and executing the rest of
[`../backend-functionalities.md`](../backend-functionalities.md). Written up
2026-09-07. Expect to edit this as you go.

---

## Part 1 — Docker, explained from zero

### The problem Docker solves

The backend needs a specific world to run in: Python 3.14, a set of libraries
(`fastapi`, `asyncpg`, …), environment variables, and a Postgres database. Right
now that world lives on one laptop, assembled by hand. That causes three classic
problems:

1. **"Works on my machine."** A teammate, a deploy server, or future-you on a new
   laptop has a different Python, a different OS, a missing system library — and
   the app breaks in ways that are annoying to debug.
2. **Setup is a checklist.** Install Python, install `uv`, install Postgres,
   create a database, set env vars… every new environment repeats it.
3. **The laptop gets cluttered.** Postgres running as a background service,
   version conflicts between projects, etc.

### What Docker actually is

Docker packages the app **together with its entire environment** into one
artifact that runs the same way everywhere.

Analogy: a **shipping container**. Before containers, cargo was loaded piece by
piece and every ship/truck/crane handled it differently. Standardize the box and
any ship can carry any container without caring what is inside. Docker is that box
for software.

Two core concepts:

| Term | What it is | Analogy |
|---|---|---|
| **Image** | A frozen, read-only snapshot: OS + Python + code + dependencies. Built once. | A class, or a cake recipe |
| **Container** | A running instance of an image. Many can be started from one image. | An object, or an actual cake |

You **build** an image, then **run** it as a container.

### The files

**`Dockerfile`** — the recipe for *this* image. A sequence of steps: start from an
official Python image → copy the code in → install dependencies → on start, run
uvicorn. Docker executes it top to bottom and produces an image.

**`docker-compose.yml`** — a way to run *multiple* containers together with one
command. The backend is really two pieces: the FastAPI server **and** a Postgres
database. Compose declares both services, how they connect, and their env vars;
`docker compose up` starts both, wired together.

Why the plan wants compose *"for local Postgres"*: instead of installing Postgres
on the machine, you get a throwaway Postgres in a container. Delete it, recreate
it, run a different version per project — no mess.

### "Dockerize" = the verb

To **dockerize** an app means "write the `Dockerfile` (and compose file) so the
app can run as a container." That is the checklist item. Once done:

```
docker compose up      # whole backend + db running
docker compose down    # all gone, laptop clean
```

### Why this project needs it

- **Portfolio credibility** — "clone the repo, run `docker compose up`, it works"
  is what reviewers expect.
- **Local Postgres without the install** — test migrations and queries against a
  real Postgres that can be wiped anytime.
- **Deployment later** — most hosting (Render, Railway, Fly.io, AWS) takes a
  Docker image directly. Dockerizing now makes deploy mostly free later.
- **One source of truth for the environment** — the `Dockerfile` *is* the setup
  documentation, and it cannot drift out of date because it is what actually runs.

Docker is not strictly required to keep building features — `uv run uvicorn`
works fine. It is an infrastructure investment that pays off at "show it to
someone" and "deploy it" time. Doing it at the end of Phase 0, while the app is
still small, is the right call.

---

## Part 2 — Finish Phase 0

Two items look unchecked (CORS, Docker), plus secret-hygiene cleanup flagged in
[`cors-and-secrets.md`](./cors-and-secrets.md) that should close first.

### Step 0.1 — Verify CORS is actually done

The code in `backend/main.py` (CORS middleware block) and `backend/core/config.py`
(`ALLOWED_ORIGINS`) already implements it. Confirm it works, then tick the box.

1. Make sure `.env` has
   `ALLOWED_ORIGINS=http://localhost:8081,http://localhost:19006`.
   Note: `backend/env.example` still says `CORS_ORIGINS` — that name is wrong, the
   code reads `ALLOWED_ORIGINS`.
2. Start the server from `backend/`: `uv run uvicorn main:app --reload`
3. Send a preflight request (Git Bash):
   ```bash
   curl -i -X OPTIONS http://localhost:8000/api/v1/ \
     -H "Origin: http://localhost:8081" \
     -H "Access-Control-Request-Method: GET"
   ```
4. Pass = response contains
   `access-control-allow-origin: http://localhost:8081`. Try a junk origin
   (`http://evil.test`) and confirm the header is **absent**.
5. Tick the CORS box in both checklists.

### Step 0.2 — Secret hygiene (before Docker)

`backend/.env` is committed with live credentials. Order matters:

1. **Rotate every leaked secret** — the only step that closes the leak:
   - Supabase → Settings → Database → reset database password → update
     `DATABASE_URL` in the local `.env`
   - Supabase → Settings → API Keys → roll `SUPABASE_SECRET_KEY`
   - Clerk → API Keys → roll `CLERK_SECRET_KEY`
2. Add `.env` to `backend/.gitignore` (add a line: `.env`).
3. Stop tracking it: `git rm --cached backend/.env`, then commit. The local file
   stays.
4. Rename `env.example` → `.env.example` (leading dot, conventional) and fix
   `CORS_ORIGINS` → `ALLOWED_ORIGINS` inside it.
5. Optional: scrub it from git history with `git filter-repo` or BFG. For a solo
   portfolio repo that has never been pushed publicly, rotation + removal is
   usually enough — decide based on whether this repo is or will be public.

### Step 0.3 — Dockerize

`Dockerfile`, `docker-compose.yml`, and `.dockerignore` all exist but are
**empty**. What each needs and why:

**`.dockerignore`** — keeps junk out of the image (faster builds, no leaked
`.env`):
```
.venv
__pycache__
*.pyc
.env
.git
migrations/versions/__pycache__
```

**`Dockerfile`** — the plan:
1. Start from an image matching `requires-python = ">=3.14"` — e.g.
   `python:3.14-slim`. If 3.14 images are not on Docker Hub yet, that is a signal
   to loosen `pyproject.toml` to `>=3.12` — worth checking.
2. Install `uv` (copy from `ghcr.io/astral-sh/uv` or `pip install uv`).
3. Set a working directory (`/app`).
4. Copy `pyproject.toml` and `uv.lock` first, run `uv sync --frozen --no-dev` —
   copying these *before* the source lets Docker cache the dependency layer and
   only reinstall when deps change.
5. Copy the rest of the source.
6. `EXPOSE 8000`.
7. `CMD` runs `uv run uvicorn main:app --host 0.0.0.0 --port 8000` (no `--reload`
   in the image itself).

**`docker-compose.yml`** — two services:
1. **`db`**: image `postgres:17`, set
   `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`, map `5432:5432`, add a named
   volume so data survives restarts, add a `healthcheck` using `pg_isready`.
2. **`api`**: `build: .`, `depends_on` the db with
   `condition: service_healthy`, map `8000:8000`, load env from `.env`, and
   **override `DATABASE_URL`** to point at `db` instead of Supabase —
   `postgresql://user:pass@db:5432/cahoots` (hostname is the service name `db`).
   Mount the source as a volume and add `--reload` to the command for dev
   live-reload.

**Decision — local Postgres vs Supabase in dev:**
- *Local Postgres*: fast, offline, wipeable, no risk to real data. Downside: a
  second database whose schema must be kept in sync (`alembic upgrade head`
  against it).
- *Keep using Supabase*: one database, already has the schema. Simpler now, but
  every dev test hits the real cloud DB.

Recommendation: set up the local Postgres service (portfolio-standard, decouples
from Supabase), knowing `DATABASE_URL` can point back at Supabase anytime.

**Test it:**
```
docker compose up --build
```
- `docker compose ps` shows both containers healthy
- `curl http://localhost:8000/` → `{"status":"ok"}`
- Run migrations against the container DB:
  `docker compose exec api uv run alembic upgrade head`
- `curl http://localhost:8000/test-db-connection` → `{"status":"connected", ...}`

Then tick the Docker box. **Phase 0 done.**

---

## Part 3 — Feature phases (1 → 9)

Build order from [`../backend-functionalities.md`](../backend-functionalities.md):
**0 → 1 → 2 → 3 → 4 → 6 → 5 → 7 → 8**, with 9 running continuously.

Each `plan/phase-N/README.md` currently only has the checklist. Flesh out notes as
you go, the way `phase-0/` accumulated docs.

### General rhythm for every checklist item

1. **Model** (if it needs a table): write `backend/models/<domain>.py` following
   the pattern in [`database-setup-walkthrough.md`](./database-setup-walkthrough.md),
   register it in `backend/models/__init__.py`.
2. **Migration**: `uv run alembic upgrade head` first, then
   `uv run alembic revision --autogenerate -m "..."`, review the file,
   `uv run alembic upgrade head`.
3. **Schema**: Pydantic request/response models in `backend/schemas/<domain>.py` —
   never accept or return raw dicts.
4. **Service**: business logic in `backend/services/<domain>.py` — keep routers
   thin.
5. **Router**: endpoints in `backend/routers/<domain>.py` (files already stubbed),
   wire dependencies.
6. **Test**: `pytest` (dev deps have `pytest` + `pytest-asyncio` + `httpx`) and/or
   hit `/docs` manually.
7. Tick the box, commit.

### Phase 1 — Auth (everything depends on it)

1. Build the `User` model + migration (example in
   [`database-setup-walkthrough.md`](./database-setup-walkthrough.md)).
2. Write a `get_current_user` dependency: read `Authorization: Bearer <jwt>`,
   fetch Clerk's JWKS from `CLERK_JWKS_URL`, verify the token signature with
   `pyjwt`, extract the user id from claims, load the `users` row. 401 on any
   failure.
3. `GET /me` — thin route: `Depends(get_current_user)` → return the profile.
4. Clerk sync webhook: `POST /webhooks/clerk` — verify the webhook signature
   (Clerk uses Svix); on `user.created` insert a `users` row with Clerk's id as
   the PK. The only place `users` rows get created.
5. From here on, add `Depends(get_current_user)` to every real route.
6. **Test**: grab a real JWT from a Clerk test user, call `GET /me` with and
   without it.

### Phase 2 — Events CRUD

1. Models: `Event`, `EventMember` (+ a `MemberRole` enum: organizer/guest).
   `EventMember` is the join table between users and events.
2. A `require_event_role(...)` dependency checking the current user's row in
   `event_members` for the given `event_id`.
3. The 5 endpoints. On `POST /events`, also insert an `event_members` row making
   the creator the organizer. `GET /events` filters to events where the user has
   an `event_members` row. `PATCH`/`DELETE` require organizer role.
4. **Test**: create event, list it, have a second user confirm they cannot see or
   edit it.

### Phase 3 — Invites

1. `Invite` model: token (random URL-safe string), `event_id`, optional expiry,
   used flag.
2. `POST /events/{id}/invite` (organizer only) → returns a token/link.
3. `POST /invites/{token}/accept` → validates token, creates the `event_members`
   row as guest. Handle: already a member (idempotent success), invalid token
   (404), expired (410).
4. **Test**: unlocks real multi-user testing — invite user B, have them accept,
   confirm they now see the event.

### Phase 4 — Itinerary (first "real" feature)

1. `ItineraryItem` model: `event_id` FK, title, times, a `position` int for
   ordering.
2. CRUD endpoints, all guarded by event membership. `GET` returns items ordered
   by `position`.
3. `PATCH .../itinerary/reorder` — accepts an ordered list of IDs, rewrites
   `position` on each in one transaction.
4. **Test**: add 3 items, reorder, confirm order persists.

### Phase 6 — Expenses (before realtime — self-contained, demo-able)

1. Models: `Expense` (amount as `Numeric(10,2)`, payer FK, split type enum),
   `ExpenseShare` (per-member owed amount).
2. On `POST`, compute shares from split type (equal = amount / member count;
   custom = provided amounts, validate they sum to the total).
3. `GET /events/{id}/settlement` — **write this as a pure function**
   `simplify_debts(balances) -> list[(debtor, creditor, amount)]` in `services/`,
   separate from any DB code.
4. **Test**: unit-test `simplify_debts` hard with several scenarios — the
   showcase portfolio artifact.

### Phase 5 — Realtime

1. `WebSocket /ws/events/{event_id}` endpoint, auth via a token query param
   (browsers cannot set WS headers).
2. An in-memory `dict[event_id, set[WebSocket]]` connection registry.
3. After any itinerary write, broadcast the change to that event's sockets.
4. Presence: track who is connected per event, broadcast join/leave.
5. **Test**: open two `websocat` / browser clients on the same event, change
   itinerary in one, see it in the other.

### Phase 7 — Polls (reuses Phase 5 infra)

1. Models: `Poll`, `PollOption`, `PollVote` (unique on `(poll_id, user_id)` so a
   vote replaces).
2. Create poll+options, cast/change vote, get results.
3. Broadcast updated tallies over the event WebSocket on each vote.
4. `POST /polls/{id}/close` (organizer) — optionally write the winning option
   back to the event.

### Phase 8 — Notifications

1. `POST /me/push-token` — store the Expo token on the `users` row.
2. On new expense / new poll / itinerary change, use FastAPI `BackgroundTasks` to
   POST to Expo's push API for the relevant members.
3. Skip Celery + Redis unless that is specifically wanted on the resume —
   `BackgroundTasks` is enough here.

### Phase 9 — Polish (continuous, not at the end)

After each phase, spend ~20 minutes on: custom exception handlers for consistent
error JSON, Pydantic validation on every input, `/docs` descriptions and
examples. Save RLS policies, the full pytest sweep, and the README architecture
diagram for a dedicated pass before calling it "portfolio-ready."

---

## Progress log

- 2026-09-07 — guide written. Phase 0: CORS implemented (needs verify + tick),
  secret hygiene pending, Docker files empty.
