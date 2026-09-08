# Execution Guide — Docker primer + full backend build order

Working notes for finishing Phase 0 and executing the rest of
`[../backend-functionalities.md](../backend-functionalities.md)`. Written up
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


| Term          | What it is                                                                   | Analogy                      |
| ------------- | ---------------------------------------------------------------------------- | ---------------------------- |
| **Image**     | A frozen, read-only snapshot: OS + Python + code + dependencies. Built once. | A class, or a cake recipe    |
| **Container** | A running instance of an image. Many can be started from one image.          | An object, or an actual cake |


You **build** an image, then **run** it as a container.

### The files

`Dockerfile` — the recipe for *this* image. A sequence of steps: start from an
official Python image → copy the code in → install dependencies → on start, run
uvicorn. Docker executes it top to bottom and produces an image.

`docker-compose.yml` — a way to run *multiple* containers together with one
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
`[cors-and-secrets.md](./cors-and-secrets.md)` that should close first.

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

`backend/.env` is committed with live credentials. "Roll" / "rotate" a key =
generate a fresh one and kill the old one, so the copy sitting in git history
stops working. Adding `.env` to `.gitignore` only prevents *future* leaks — it
does not un-leak what is already in history. Rolling is the step that actually
closes it.

Order matters:

1. **Rotate every leaked secret:**
  **Clerk secret key** (`CLERK_SECRET_KEY`) — Clerk allows multiple secret keys
   at once, so this rolls with no downtime:
  - Clerk Dashboard → your app → Configure → API Keys → **Secret keys** section
  - "Add new key", name it e.g. `cahoots_backend_secret_key`
  - Reveal (👁) or copy (📋) its value → paste into `backend/.env` as
  `CLERK_SECRET_KEY=sk_test_...`
  - On the **old** key's row (`default`), click the trash icon → confirm
  - The Clerk **publishable key** (`pk_test_...`) has no "Add new key" — that is
  expected. It is public by design, not a secret, nothing to roll.
   **Supabase secret key** (`SUPABASE_SECRET_KEY`) — bypasses Row Level Security,
   full DB access:
  - Supabase → Project Settings → API Keys → **Secret keys**
  - "Create new secret key" → copy the value (shown once) → into `.env`
  - Restart backend, verify it still connects
  - Delete / revoke the old key's row
  - If only legacy `anon` / `service_role` JWT keys exist instead: Settings →
  API Keys → JWT Keys → "Rotate JWT secret" (also invalidates `anon` and logs
  out Supabase Auth sessions — fine pre-launch since auth is Clerk here)
   **Supabase database password** (inside `DATABASE_URL`):
  - Supabase → Project Settings → Database → "Reset database password"
  - Update the password portion of `DATABASE_URL` in `.env`, restart, verify
   **Not secret, nothing to do:** `CLERK_JWKS_URL` (public endpoint publishing
   Clerk's public verification keys), `CLERK_PUBLISHABLE_KEY`,
   `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_URL`.
2. Add `.env` to `backend/.gitignore` (add a line: `.env`).
3. Stop tracking it: `git rm --cached backend/.env`, then commit. The local file
  stays. Rolling is pointless if `.env` is still tracked — the next commit
   re-leaks the new values.
4. Rename `env.example` → `.env.example` (leading dot, conventional) and fix
  `CORS_ORIGINS` → `ALLOWED_ORIGINS` inside it.
5. Optional: scrub it from git history with `git filter-repo` or BFG. For a solo
  portfolio repo that has never been pushed publicly, rotation + removal is
   usually enough — decide based on whether this repo is or will be public.

Later, in Phase 1: the Clerk webhook signing secret (`whsec_...`) is also
sensitive — keep it in `.env` only, never commit it.

### Step 0.3 — Dockerize

`Dockerfile`, `docker-compose.yml`, and `.dockerignore` all exist but are
**empty**. What each needs and why:

`.dockerignore` — keeps junk out of the image (faster builds, no leaked
`.env`):

```
.venv
__pycache__
*.pyc
.env
.git
migrations/versions/__pycache__
```

`Dockerfile` — full content, with each line explained:

```dockerfile
# ---- Base image ----
FROM python:3.14-slim

# ---- Bring in uv ----
# uv ships as a single static binary. Copy it straight out of Astral's official
# image instead of pip-installing it. Fast, no extra layers.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ---- Build-time env ----
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1
# UV_COMPILE_BYTECODE  — precompile .pyc on install, slightly faster startup
# UV_LINK_MODE=copy    — copy packages into .venv instead of hardlinking
#                        (hardlinks can fail across Docker's layer filesystem)
# PYTHONUNBUFFERED      — don't buffer stdout/stderr, so logs show up live

# ---- Working directory ----
WORKDIR /app

# ---- Dependencies (cached layer) ----
# Copy ONLY the dependency manifests first. Docker caches each instruction as a
# layer; as long as these two files don't change, the slow `uv sync` below is
# reused from cache even when source code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
# --frozen  — install exactly what's in uv.lock, error if the lock is stale
# --no-dev  — skip the [dependency-groups] dev deps (pytest, httpx)

# ---- Application code ----
COPY . .

# ---- Network ----
EXPOSE 8000
# Documentation only — actual port mapping is in docker-compose.yml.

# ---- Startup command ----
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# --host 0.0.0.0  — listen on all interfaces so Docker can forward host traffic
#                   in (default 127.0.0.1 is only reachable inside the container)
# no --reload     — dev-only; compose adds it back for local use
```

Notes:

- `python:3.14-slim` should exist (3.14 shipped Oct 2025). If
`docker compose up --build` fails with "manifest unknown", fall back to
`python:3.13-slim` and set `requires-python = ">=3.13"` in `pyproject.toml`.
- Build context is `backend/` — so `COPY . .` puts `main.py` at `/app/main.py`,
matching `WORKDIR /app` and the router imports (`from routers import ...`).
- No `.env` in the image (`.dockerignore` excludes it). `pydantic-settings` then
reads config from real environment variables, which `docker-compose.yml`
injects. Secrets stay out of the image.
- `package = false` in `pyproject.toml` means uv won't build the app as a
package, so one `uv sync` after copying the manifests is enough.
- Optional hardening for later (skip now): run as non-root
(`RUN useradd -m app && chown -R app:app /app` then `USER app`), and a
multi-stage build to drop uv + caches from the final image before deploy.

`docker-compose.yml` — full content:

```yaml
services:
  api:
    build: .                     # uses ./Dockerfile
    command: uv run --frozen uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file:
      - .env                     # DATABASE_URL (Supabase), Clerk keys, etc.
    environment:
      DEBUG: "true"
      ALLOWED_ORIGINS: http://localhost:8081,http://localhost:19006
    volumes:
      - .:/app                   # live-mount source so --reload sees edits
      - /app/.venv               # anon volume: don't let the mount shadow the image's .venv
```

Decision recorded: **stay on Supabase, no local Postgres container.** Supabase is
one of the things this project is meant to teach, and one hosted DB is less to
juggle. So there is no `db` service — the app reads `DATABASE_URL` straight from
`.env`, pointing at Supabase. If a local Postgres is ever wanted, the earlier
draft (a `db: postgres:17` service + a `DATABASE_URL` override + `depends_on` with
a healthcheck) is the way to add it back.

Why the remaining pieces are there:

- `env_file: .env` — supplies `DATABASE_URL` and the Clerk/Supabase keys. No
override needed now; the app connects to Supabase exactly as it does outside
Docker.
- `volumes: - .:/app` **+** `- /app/.venv` — the first bind-mounts your source so
`--reload` picks up edits without a rebuild. But that mount would also hide the
`.venv` the image built at `/app/.venv`; the second (anonymous) volume shields
it.
- `command:` **with** `--reload` — dev convenience, overrides the image's `CMD`.
`--frozen` stops `uv run` from trying to re-sync inside the container.

Compose is still worth having even for a single service: `docker compose up`
beats a long `docker run -p ... --env-file ... -v ...` line, and it is the
expected entry point for anyone cloning the repo.

**Test it** (run from `backend/`):

```
docker compose up --build
```

- `docker compose ps` shows the `api` container up
- `curl http://localhost:8000/` → `{"status":"ok"}`
- `curl http://localhost:8000/test-db-connection` → `{"status":"connected", ...}`
(this confirms the container can reach Supabase — no local migration step
needed, Supabase already has the schema)
- edit a file, confirm `--reload` restarts the server
- `docker compose down` stops it

Then tick the Docker box. **Phase 0 done.**

---



## Part 3 — Feature phases (1 → 9)

Build order from `[../backend-functionalities.md](../backend-functionalities.md)`:
**0 → 1 → 2 → 3 → 4 → 6 → 5 → 7 → 8**, with 9 running continuously.

Each `plan/phase-N/README.md` currently only has the checklist. Flesh out notes as
you go, the way `phase-0/` accumulated docs.

### General rhythm for every checklist item

1. **Model** (if it needs a table): write `backend/models/<domain>.py` following
  the pattern in `[database-setup-walkthrough.md](./database-setup-walkthrough.md)`,
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
  `[database-setup-walkthrough.md](./database-setup-walkthrough.md)`).
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

