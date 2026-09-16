# Phase 1 · Item 4 — Protect all routes with `Depends(get_current_user)`

**Goal:** every route under `events`, `invites`, `itinerary`, `polls` (and
anything added later) requires a valid, synced user. Builds on item 1
(`get_current_claims` — verifies the JWT) and item 3 (the sync webhook —
populates `users`).

---

## Background: two dependencies, not one

- `get_current_claims` (item 1, `core/security.py`) — verifies the JWT
signature/issuer/expiry against Clerk's JWKS, returns the raw **claims
dict** (`sub`, `iss`, `exp`, …). Proves the token is real. Says nothing
about whether that user exists in *our* database.
- `get_current_user` (this item) — depends on `get_current_claims`,
then loads the matching row from `users` in Postgres. Proves the token is
real **and** the user is provisioned in our system. Returns the actual
`User` model, not a claims dict.

Routes should depend on `get_current_user`, not `get_current_claims` —
they need a real user object to do anything useful (`user.id` for
ownership checks, `user.email`, etc.), and `get_current_user` re-verifies
the token anyway (it depends on `get_current_claims` internally).

---



## 1. `get_current_user` — `backend/core/security.py`

```python
from models.users import User
from database.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

async def get_current_user(
    claims: dict = Depends(get_current_claims),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await session.get(User, claims["sub"])
    if not user:
        raise HTTPException(401, "User not found", headers={"WWW-Authenticate": "Bearer"})
    return user
```

**Import gotcha (bit us during this item):** use `from models.users import User` and `from database.database import get_session` — **not**
`from backend.models import User` / `from backend.database import get_session`. There's no `backend` package; the app runs with `backend/`
itself as the root, same as every other file in this repo (`core.config`,
`routers.auth`, etc. all import bare, no `backend.` prefix). The
`backend.*` form crashes at startup with `ModuleNotFoundError: No module named 'backend'`.

`AsyncSession` **import:** use `sqlalchemy.ext.asyncio.AsyncSession`, matching
`database/database.py` (that's the class `get_session()` actually yields).
`sqlmodel.ext.asyncio.session.AsyncSession` is a *different* class with the
same name — harmless at runtime here, but a type mismatch waiting to bite a
type checker or an `isinstance` check later.

**401 vs 404 on "user not found":** went with 401 (not 404) to keep every
failure mode of the `get_current_claims` → `get_current_user` chain on one
status code — callers handle one "you're not authenticated" case instead of
two. Kept the `WWW-Authenticate: Bearer` header since it's still an
auth-scheme response. (404 is defensible too — "no such resource" — just
drop the header if you go that way, it doesn't belong on a 404.)

---



## 2. Protect the routers

Per-router `dependencies=[...]`, not per-route `Depends(...)` on each
endpoint. Reasoning: these four routers are meant to be **100%
authenticated** (see `README.md`'s Phase 1 goal). Per-route protection is
opt-in — write an endpoint, forget the `Depends(...)` line, and it ships
unauthenticated with no error, nothing catching it but manual review.
Per-router protection is opt-out — new endpoints are protected by default
just by virtue of which file they're in.

```python
# backend/routers/events.py
from fastapi import APIRouter, Depends
from core.security import get_current_user

router = APIRouter(
    prefix="/events",
    tags=["events"],
    dependencies=[Depends(get_current_user)],  # only authenticated users can access this router
)
```

Same edit in `invites.py`, `itinerary.py`, `polls.py`.

Note: `dependencies=[...]` on `APIRouter` runs `get_current_user` before
every route on that router, but does **not** inject its return value as an
argument. An endpoint that also needs the `User` object itself still
declares `user: User = Depends(get_current_user)` in its own signature —
FastAPI dedupes the call per-request, so it's not hitting the DB twice.

- [x] `events.py`
- [x] `invites.py`
- [x] `itinerary.py`
- [x] `polls.py`

`auth.py`'s `/whoami` stays on `get_current_claims` — it's a
claims-only debug probe, useful independent of whether a `users` row exists.
Don't swap it permanently (see testing section below for why it got swapped
*temporarily* during this item).

---



## 3. Testing — full sequence

These routers are still empty stubs (no endpoints written yet), so there's
nothing on them to curl directly. The workaround: temporarily point
`/auth/whoami` at `get_current_user` instead of `get_current_claims`, run
the tests, then revert. Once a real endpoint exists on one of the four
routers, test that directly instead and skip the swap.

### 3a. Get the server + webhook path running

You need **three things running at once** for a full test (server, tunnel,
and — only if testing the sync path — the webhook wired up in Clerk):

```bash
# terminal 1
uv run uvicorn main:app --reload

# terminal 2 — only needed if testing signup → Supabase sync
ngrok http 8000
```

**Why ngrok:** Clerk's servers can't reach `localhost:8000` directly. ngrok
opens a public HTTPS tunnel back to your machine — without it, the sync
webhook (item 3) has nowhere to deliver to, and `user.created` events fail
silently on Clerk's end.

**Gotcha — free-plan ngrok URLs change every restart.** If you've
restarted ngrok since last session, the URL Clerk has on file is stale.
Check/update it:

Clerk Dashboard → Configure → Webhooks → your endpoint → confirm the URL
is `https://<current-ngrok-url>/api/v1/webhooks/clerk` and `user.created`
is checked under subscribed events.

**Gotcha — duplicate endpoints.** If you clicked "Add Endpoint" fresh each
time ngrok gave you a new URL (instead of editing the existing one), you
can end up with multiple endpoint entries in the dashboard — some pointing
at dead URLs. Check you're looking at (and that Clerk is actually using)
the currently-live one.

### 3b. Get a test user actually synced to Supabase

`user.created` only fires on a **genuine new signup** — signing in to an
account made earlier does not re-trigger it. To get a fresh `users` row:

1. Go to your Clerk instance's Account Portal and **sign up** (not sign in)
  with a brand-new test email:
   `https://<your-instance>.accounts.dev/sign-up`
2. Confirm the row landed: `SELECT * FROM users WHERE id = '<clerk user id>';`
  in Supabase, or check Clerk Dashboard → Users to get the id first.

**Gotcha — delivery can take a few minutes.** Clerk's webhooks run on Svix,
which retries failed deliveries with increasing backoff (not instant
forever-retry). If your first attempt failed — e.g. ngrok/the endpoint URL
wasn't correctly wired up yet the moment you signed up — the row won't
appear until a later scheduled retry succeeds, which can be several minutes
after signup. Not a bug; check the endpoint's delivery/message-attempts log
in the dashboard to confirm (it'll show failed attempts followed by a
success, timestamps apart).

If nothing shows up at all after a while: check the delivery log for a
non-200 response (signature failure → usually
`CLERK_WEBHOOK_SIGNING_SECRET` in `.env` doesn't match the endpoint's actual
secret in Clerk's dashboard; 500 → check your `uvicorn` terminal for a
traceback from `_handle_user_created`).

### 3c. Get a token for that user

No frontend exists yet in this repo, so skip `getToken()` from app code —
use the Account Portal + browser console instead:

1. Sign into the Account Portal as your synced test user.
2. Open dev console (F12), run:
  ```js
   await window.Clerk.session.getToken()
  ```
3. Copy the returned string.

**Gotcha — tokens expire in ~60s and auto-rotate.** Grab a fresh one
immediately before each curl call; a token copied a few minutes ago will
correctly 401 on expiry, which is not a bug.

**Not this:** Clerk Dashboard → "Customize session token" screen. That page
configures what *claims* go into future tokens — it doesn't hand you a
copyable token.

### 3d. Swap `whoami` to test `get_current_user`

```python
# backend/routers/auth.py — TEMPORARY, revert after testing
@router.get("/whoami")
async def whoami(user: User = Depends(get_current_user)):
    return user
```



### 3e. Run the three cases

```bash
# 1. no token → 401
curl -i http://localhost:8000/api/v1/auth/whoami

# 2. valid token, synced user → 200, body is user fields (id/email/display_name),
#    not claims fields (sub/iss/exp) — confirms get_current_user, not get_current_claims, ran
curl -i http://localhost:8000/api/v1/auth/whoami \
  -H "Authorization: Bearer <fresh token>"

# 3. valid token, sub has no matching `users` row → 401 "User not found"
#    (use a token from a user who signed up but hasn't synced yet, or any
#    token after deleting their row manually)
curl -i http://localhost:8000/api/v1/auth/whoami \
  -H "Authorization: Bearer <token for unsynced user>"
```

`-i` shows the status line in the output — check it directly rather than
adding `-v`.

### 3f. Revert

```python
# backend/routers/auth.py — back to normal
@router.get("/whoami")
async def whoami(current_claims: dict = Depends(get_current_claims)):
    return current_claims
```

- [x] Tested case 1 (no token → 401)
- [x] Tested case 2 (valid token, synced user → 200)
- [ ] Tested case 3 (valid token, unsynced user → 401)
- [x] Reverted `whoami`

---



## Files touched


| File                           | Change                                              |
| ------------------------------ | --------------------------------------------------- |
| `backend/core/security.py`     | added `get_current_user`                            |
| `backend/routers/events.py`    | added `dependencies=[Depends(get_current_user)]`    |
| `backend/routers/invites.py`   | same                                                |
| `backend/routers/itinerary.py` | same                                                |
| `backend/routers/polls.py`     | same                                                |
| `backend/routers/auth.py`      | unchanged (temporarily swapped during testing only) |




## Deferred / follow-ups

- No real endpoints exist yet on `events`/`invites`/`itinerary`/`polls` —
once the first one is written, prefer testing against it directly instead
of the `whoami` swap trick.
- Case 3 (unsynced user → 401) not yet explicitly re-verified after the
import fixes — worth a final pass before closing this item out.

