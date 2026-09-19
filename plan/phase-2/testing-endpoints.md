# Phase 2 · Testing the events endpoints (with a Clerk bearer token)

Every route on `/api/v1/events/*` sits behind `Depends(get_current_user)`
([`routers/events.py`](../../backend/routers/events.py)), which itself depends
on `get_current_claims` ([`core/security.py`](../../backend/core/security.py)).
That means every request needs a **real, unexpired Clerk-signed JWT** in the
`Authorization` header — there's no way to fake one locally, since
`verify_token()` checks the signature against Clerk's live JWKS.

---

## 1. Get a bearer token

Pick whichever is fastest right now:

- **Browser console via `window.Clerk` (usually the fastest — no dashboard digging)**
  1. Open any page where Clerk's JS SDK is loaded and you're signed in — e.g.
     your Expo app running in web mode (`npx expo start --web`), or Clerk's
     own hosted sign-in/account portal page for your instance.
  2. Open devtools → Console, and run:
     ```js
     await window.Clerk.session.getToken()
     ```
  3. It logs the raw JWT string — copy it.
  - This works because the Clerk SDK attaches a `Clerk` object to `window` on
    any page it's loaded on; you don't need backend/frontend code changes to
    read it.

- **Clerk Dashboard (if you can find the right page — the layout moves around)**
  - Newer dashboards don't have a standalone "Sessions" nav item. Instead:
    **Users** → click into a specific user → look for an **Active sessions**
    section on their profile page → a session there may expose a way to copy
    its token, or at least confirm one exists so `window.Clerk` (above) has
    something to return.
  - If you're using a JWT template, **JWT Templates** → your template →
    **Testing** tab also gives you a ready-made token without needing a real
    signed-in session.
  - ⚠️ Wherever you get it from, Clerk session tokens are short-lived (~60s
    by default before needing a refresh) — grab one right before you test,
    not ahead of time.

- **From the running frontend/Expo app's own code**
  - Wherever you call Clerk's client SDK, log the result of `getToken()`
    (e.g. `useAuth().getToken()`) and copy it from the console/logs.

Either way you end up with a long `eyJhbGciOi...` string. That's your `<TOKEN>`.

---

## 2. Start the backend

```bash
cd backend
docker compose up --build
```

(or, without Docker: `uv run uvicorn main:app --reload` from `backend/`)

Confirm it's up:

```bash
curl http://localhost:8000/
# {"status": "ok"}
```

`.env` must have `CLERK_JWKS_URL` and `CLERK_ISSUER` set to your Clerk
instance — see [`.env.example`](../../backend/.env.example) — otherwise
`verify_token()` will fail to resolve the signing key.

---

## 3. Sanity-check auth itself before touching events

Use the existing probe endpoints first so you know the token is good before
you blame the events code:

```bash
# no token -> 401 "Missing bearer token"
curl -i http://localhost:8000/api/v1/auth/whoami

# garbage token -> 401 "Invalid or expired token"
curl -i http://localhost:8000/api/v1/auth/whoami \
  -H "Authorization: Bearer garbage"

# real token -> 200 with decoded claims (sub, iss, exp, ...)
curl -i http://localhost:8000/api/v1/auth/whoami \
  -H "Authorization: Bearer <TOKEN>"

# real token -> 200 with the DB user row (fails 401 "User not found" if the
# Clerk user was never synced into the `users` table via the webhook)
curl -i http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <TOKEN>"
```

Don't move on to events until `/auth/me` returns 200 — `create_event` and
`get_events` both need `user.id` to exist in the `users` table.

---

## 4. Test the events endpoints

Export the token once so the rest of the commands stay short:

```bash
export TOKEN="<paste the token here>"
```

### `POST /api/v1/events/create`

```bash
curl -i -X POST http://localhost:8000/api/v1/events/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "title": "Beach trip",
        "description": "Weekend getaway",
        "location": "Santa Cruz",
        "start_date": "2026-10-03",
        "end_date": "2026-10-05",
        "cover_image_url": null
      }'
```

Expect `201` with the created event, including a generated `id` and
`created_by` set to your Clerk user id. Save that `id` — you'll want it once
`GET /events/{event_id}` etc. exist (they're still unchecked in
[`README.md`](README.md)).

Also check the negative cases:

- Missing `title` → `422` (Pydantic validation error).
- No/garbage token → `401`, same as the auth probes above.

### `GET /api/v1/events/`

```bash
curl -i http://localhost:8000/api/v1/events/ \
  -H "Authorization: Bearer $TOKEN"
```

Expect `200` with a list containing the event(s) you just created (this route
filters to events where `EventMember.user_id == current user`, so an event
created by a *different* Clerk user should **not** show up here).

---

## 5. Faster iteration: use `/docs` instead of curl

FastAPI's Swagger UI has an **Authorize** button (it appears because of
`HTTPBearer` in `core/security.py`):

1. Open http://localhost:8000/docs
2. Click **Authorize**, paste the raw token (no `Bearer ` prefix needed — Swagger adds it), click **Authorize** again, then **Close**.
3. Every "Try it out" call from then on carries the token automatically.

This is worth doing since Clerk session tokens expire fast — re-authorizing
in Swagger is quicker than re-exporting `$TOKEN` in the terminal each time.

---

## Common failure modes

| Symptom | Likely cause |
| --- | --- |
| `401 Missing bearer token` | Forgot the `Authorization: Bearer ...` header |
| `401 Invalid or expired token` | Token expired (grab a fresh one — they're short-lived) or `CLERK_JWKS_URL`/`CLERK_ISSUER` in `.env` don't match the instance that issued the token |
| `401 User not found` | Token is valid but that Clerk user was never synced to the `users` table — check the Clerk webhook ([`clerk-webhook-user-sync.md`](../phase-1/clerk-webhook-user-sync.md)) actually fired |
| `422` on create | Request body missing `title` or has a bad date format (`YYYY-MM-DD`) |
| Empty list from `GET /events/` | You're authenticated as a user who isn't a member of any event — create one first |
