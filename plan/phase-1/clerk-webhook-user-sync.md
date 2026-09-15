# Phase 1 · Item 3 — Clerk sync webhook

**Goal:** when a user signs up via Clerk, Clerk calls our backend and we insert a
corresponding `users` row in Postgres.

> This doc will change as we go. Tick boxes as you finish them.

---

## Scope

**In scope for this item**

- A `POST /api/v1/webhooks/clerk` endpoint that verifies the request really
  came from Clerk (Svix signature check) and, on a `user.created` event,
  inserts a `users` row.
- A fix to the `users.id` column type, discovered while building this item
  (see below) — it was the wrong type to ever hold a real Clerk id.

**Not this item** (later work)

| Later item | What it adds |
| --- | --- |
| `user.updated` / `user.deleted` sync | Keeping the row in sync after signup — not built yet, only `user.created` is subscribed to in the Clerk Dashboard. |
| Item 4 | Route-wide auth enforcement — must **not** wrap this router, since Clerk calls it with no user session. |

---

## Design decisions

- **Signature verification library:** `svix` (added to `pyproject.toml`).
  Clerk delivers webhooks signed via Svix; the `svix` package verifies the
  `svix-id` / `svix-timestamp` / `svix-signature` headers against the raw
  request body and the endpoint's signing secret.
- **`Webhook` instantiated once at module level** in `routers/webhooks.py` —
  same reasoning as `jwks_client` in `core/security.py`: the secret doesn't
  change per request.
- **Verification and JSON-parsing are separate steps.** The installed `svix`
  version (2.5.0) wraps Svix's newer `standardwebhooks` package, and its
  `Webhook.verify()` returns `None` on success — it no longer hands back the
  parsed payload like older `svix` versions did. So the handler calls
  `webhook.verify(payload, headers)` purely for its side effect (raises
  `WebhookVerificationError` on a bad signature), then separately does
  `event = json.loads(payload)`.
- **Idempotency:** Svix/Clerk can redeliver the same event (at-least-once
  delivery), and the dashboard's "resend" button makes duplicates easy to
  trigger even outside real retries. The handler checks `session.get(User,
  clerk_id)` before inserting, and also catches `IntegrityError` from the
  unique constraint in case two deliveries race past that check.
- **Missing primary email is acked, not errored.** If a `user.created`
  payload has no usable email, the handler returns `200` anyway — raising
  would make Svix retry the same broken event on a fixed schedule and
  eventually disable the endpoint after enough consecutive failures.
- **Route stays public** (no `Depends(get_current_claims)`). Clerk isn't a
  logged-in user — the Svix signature check *is* this route's auth.

---

## The `users.id` type bug (found before this item could work at all)

`models/users.py` defined `id: uuid.UUID = Field(primary_key=True)`, and the
Phase 0 migration created it as a real Postgres `uuid` column. But Clerk's
native user ids are strings like `user_2g7np7Hrk0SN6kj5EDMLDaKNL0S` — not
UUIDs. Inserting one into a `uuid` column fails outright.

**Fix:** changed `users.id` to `str`, and every FK column that pointed at
`users.id` (12 columns across 7 model files) to `str` as well, so the id type
stays consistent end-to-end. No second "internal id" was introduced — Clerk's
id *is* the user's id in this app, matching what the Phase 0 docs already
assumed (`sub` is the Clerk user id — see `clerk-jwt-verification.md`).

### Columns changed (all `uuid` → `varchar`)

| Table | Column |
| --- | --- |
| `users` | `id` |
| `availability_slots` | `user_id` |
| `event_invites` | `created_by` |
| `event_members` | `user_id` |
| `events` | `created_by` |
| `expense_shares` | `user_id` |
| `expenses` | `paid_by` |
| `itinerary_comments` | `user_id` |
| `itinerary_items` | `created_by` |
| `notification_log` | `user_id` |
| `packing_items` | `assigned_to` |
| `poll_votes` | `user_id` |
| `polls` | `created_by` |

### Migration gotcha

`alembic revision --autogenerate` produced plain `ALTER COLUMN ... TYPE
VARCHAR` statements for every column above. That fails on the 12 FK columns:
Postgres won't let a foreign key's two sides disagree in type, even
mid-migration, so altering either side while the constraint still exists
raises `DatatypeMismatch: foreign key constraint ... cannot be implemented`.

**Fix applied to the migration** (`migrations/versions/20260915_2121-40a1ad678563_change_users_id_and_fks_to_text_for_.py`):
drop all 12 FK constraints first, then alter all 13 columns (`users.id` +
the 12 FKs), then recreate the 12 FK constraints pointing back at
`users.id`. Constraint names were confirmed by querying
`information_schema.table_constraints` rather than guessed.

---

## Steps

- [x] **1. Fix the `users.id` type mismatch**
  - `models/users.py` → `id: uuid.UUID` → `id: str`
  - 7 other model files → each `foreign_key="users.id"` column → `str`
  - `uv run alembic revision --autogenerate -m "change users.id and FKs to text for clerk ids"`
  - hand-edit the generated migration to drop/recreate the 12 FK constraints
    around the type changes (autogenerate doesn't do this on its own)
  - `uv run alembic upgrade head`

- [x] **2. Add the `svix` dependency**
  - `uv add svix` → added to `pyproject.toml`

- [x] **3. Add the webhook signing secret setting**
  - `core/config.py` → `CLERK_WEBHOOK_SIGNING_SECRET: str = ""`
  - `.env` / `.env.example` → same key (per-endpoint secret from the Clerk
    Dashboard, separate from `CLERK_SECRET_KEY`)

- [x] **4. Create `backend/routers/webhooks.py`**
  - `POST /webhooks/clerk`, reads `await request.body()` for the raw bytes
    (needed for signature verification — not a re-serialized Pydantic model)
  - verifies via `webhook.verify(payload, dict(request.headers))`, then
    `event = json.loads(payload)`
  - on `event["type"] == "user.created"`: extract the primary email from
    `data["email_addresses"]` (matched against `primary_email_address_id`,
    falling back to the first address), build `display_name` from
    first/last name → username → email, and insert the `User` row
    (idempotent via `session.get` + `IntegrityError` catch)
  - always returns `200` once the signature is verified, even for event
    types it doesn't act on

- [x] **5. Register the router**
  - `main.py` → `from routers import ..., webhooks` and
    `app.include_router(webhooks.router, prefix=settings.API_PREFIX)`

- [x] **6. Configure the endpoint in Clerk + local tunnel**
  - Installed `ngrok` via `winget install ngrok.ngrok` (no prior standalone
    install — only bundled copies inside `@expo/ngrok`/`npx ngrok` existed)
  - `ngrok http 8000` to get a public HTTPS URL
  - Clerk Dashboard → Configure → Webhooks → Add Endpoint →
    `https://<ngrok-url>/api/v1/webhooks/clerk`, subscribed to `user.created`
    only → copied the endpoint's Signing Secret into `.env`

- [x] **7. Test**
  - [x] Clerk Dashboard → endpoint → Testing tab → send example
    `user.created` event → `200`, row appeared in `public.users`
  - [x] confirmed via `information_schema.columns` that `public.users.id` is
    `character varying` (Supabase's own `auth.users.id` is a separate `uuid`
    column in a different schema — not the one this app uses)

---

## Bugs hit during this item (kept for the record)

- **`svix.webhooks.Webhook.verify()` returns `None`, not the parsed
  payload**, in the installed version (2.5.0) — different from older `svix`
  releases. Fixed by parsing `event = json.loads(payload)` separately after
  a successful `verify()` call.
- **`models/users.py` briefly had `id: str_schema` instead of `id: str`** —
  `str_schema` is a real importable name from `pydantic_core.core_schema`,
  so it didn't fail at import time; pydantic instead tried to build a schema
  for that function's own signature and hit an unrelated `NameError: name
  'Pattern' is not defined` deep in `pydantic_core`. Not a Python 3.14 or
  dependency bug — just the wrong name. Fixed by using the builtin `str`.
- **`ngrok` config file (`%LOCALAPPDATA%\ngrok\ngrok.yml`) was stamped
  `version: "3"` with an `agent:`-nested `authtoken`** — that's a schema
  shape the installed agent (3.3.1) didn't understand (`valid versions are:
  [1 2]`). Fixed by rewriting it to the flat v2 shape
  (`version: "2"` + top-level `authtoken:`).
- **`ERR_NGROK_121`** — winget's ngrok package version (3.3.1) was below the
  account's minimum supported agent version. Fixed with `ngrok update`
  (→ 3.39.11).
- **Migration `DatatypeMismatch` on FK columns** — see "Migration gotcha"
  above.

---

## Files touched

| File | Change |
| --- | --- |
| `backend/models/users.py` | `id` → `str` |
| `backend/models/events.py`, `itinerary.py`, `expenses.py`, `polls.py`, `availability.py`, `packing.py`, `notifications.py` | each `foreign_key="users.id"` column → `str` |
| `backend/migrations/versions/20260915_2121-40a1ad678563_...py` | **new** — type change migration, hand-adjusted for FK drop/recreate |
| `backend/pyproject.toml` | added `svix` |
| `backend/core/config.py` | added `CLERK_WEBHOOK_SIGNING_SECRET` |
| `backend/.env` / `backend/.env.example` | added `CLERK_WEBHOOK_SIGNING_SECRET` |
| `backend/routers/webhooks.py` | **new** — `POST /webhooks/clerk` |
| `backend/main.py` | registered `webhooks.router` |

---

## Deferred / follow-ups

- `user.updated` / `user.deleted` sync — not built, only `user.created` is
  subscribed to.
- Route-wide auth enforcement (Phase 1 item 4) must exclude this router.
- **ngrok URL changes every restart on the free plan** — the Clerk Dashboard
  endpoint URL needs updating each dev session unless a paid plan's static
  domain is used, or local testing is standardized on the Testing tab's
  example-event send (which doesn't require the tunnel to be freshly
  matched, as long as *some* current tunnel URL is registered).
- No handling yet for a Clerk user with zero email addresses beyond
  acking and dropping the event — revisit if the app ever allows phone-only
  or OAuth-without-email sign-up.
