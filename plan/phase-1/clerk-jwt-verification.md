# Phase 1 · Item 1 — Clerk JWT verification

**Goal:** given an incoming `Authorization: Bearer <token>`, verify Clerk's
signature and standard claims against Clerk's JWKS, and expose the decoded claims
to route handlers through one reusable dependency.

> This doc will change as we go. Tick boxes as you finish them.

---

## Scope

**In scope for this item**

- Verify signature + `iss` (issuer) + `exp` (expiration) + `nbf` (not before) against Clerk's JWKS.
- A `verify_token()` function and a `get_current_claims` FastAPI dependency.
- A test proving valid tokens pass and missing / bad / expired tokens get `401`.

**Not this item** (later Phase 1 items)


| Later item | What it adds                                                     |
| ---------- | ---------------------------------------------------------------- |
| Item 2     | `GET /me` returning a DB profile                                 |
| Item 3     | Clerk webhook that inserts the `users` row                       |
| Item 4     | Attaching the dependency to every event / itinerary / poll route |




## "Middleware" vs dependency

The checklist says "middleware" but item 4 says `Depends(get_current_user)`.
Build it as a **FastAPI dependency**, not ASGI middleware:

- composes with FastAPI's DI
- opt-in per route — `/`, `/docs`, `/redoc`, the Clerk webhook stay public
- makes the "Authorize" button appear in `/docs`

Global enforcement, if wanted, is an item-4 concern (router-level
`dependencies=[...]` or a path-skipping middleware).

### The metaphor (for when this gets confusing again)

Picture an **office building**.

- **ASGI middleware** = one security guard at the building's only entrance.
*Every* request walks past them before FastAPI even picks a route. The guard
doesn't know which office you want, so to let the mail carrier reach the public
mailroom they must hold a **hand-written "let these through" list** — you edit
that list by hand every time you add a public path.
- **FastAPI dependency** = each office hires the *same trained doorman* onto its
own door. You write one function (`get_current_claims`); any route that wants
security just declares `Depends(get_current_claims)`. No exception list — a
route is public because nobody attached the doorman.
- **The bit with no middleware equivalent:** the doorman doesn't just wave you
through — he reads your badge and **hands a slip (the verified claims) to the
person inside**. That's what `claims: dict = Depends(get_current_claims)` does:
the dependency runs first, and whatever it returns becomes an argument your
route receives. So `claims["sub"]` (the Clerk user id) is right there, no token
work in the handler.
- **Global enforcement** = hiring that one doorman for the *whole floor* at once
(`APIRouter(dependencies=[Depends(get_current_claims)])`) — still the same
doorman handing out slips, not a dumb front-door guard.

```python
# one doorman, trained once (core/security.py)
def get_current_claims(creds = Depends(bearer_scheme)) -> dict:
    return verify_token(creds.credentials)

# private — opts in, receives the slip
@router.get("/whoami")
def whoami(claims: dict = Depends(get_current_claims)):
    return claims

# public — no doorman
@router.get("/health")
def health():
    return {"status": "ok"}
```


|                    | Metaphor                                                            | Meaning                                                                          |
| ------------------ | ------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| ASGI middleware    | one guard at the only door, holding a hand-written allow-list       | you maintain a path allow-list; can't pass data to the endpoint                  |
| FastAPI dependency | each office hires the same trained doorman, who hands a slip inside | routes opt in individually; verified claims land in your function as an argument |




## Design decisions

- **Provider:** Clerk (already chosen — keys + JWKS URL are in `.env`).
- **Library:** PyJWT. It ships `PyJWKClient` with key caching. Standardize on it;
`python-jose` can be dropped later.
- **Algorithm:** `RS256` (Clerk session tokens).
- `aud` **/** `azp`**:** Clerk's default session token has no `aud`, and `azp` is
often absent for a native app. Verify signature + `iss` + `exp` + `nbf` only for
now. Hardening `azp`/`aud` (via a Clerk JWT template) is a deferred follow-up.
- **JWKS client lifetime:** instantiate `PyJWKClient` **once at module import**,
not per request, so keys are cached and Clerk isn't hit on every call.
- **Dependency returns raw claims** (a `dict`) for now. `sub` is the Clerk user id
— items 2 and 3 key off it.



## Clerk config values

From the Clerk Dashboard (instance `<your-instance>`):


| Value    | Where                                                                                                            |
| -------- | ---------------------------------------------------------------------------------------------------------------- |
| JWKS URL | `https://<your-instance>.clerk.accounts.dev/.well-known/jwks.json` (already in `.env` as `CLERK_JWKS_URL`) |
| Issuer   | `https://<your-instance>.clerk.accounts.dev` (same origin, no path) — **needs adding** as `CLERK_ISSUER`   |


---



## Steps

- [x] **1. Add** `CLERK_ISSUER` **setting**
  - `core/config.py` → add `CLERK_ISSUER: str = ""`
  - `.env` → `CLERK_ISSUER=https://[your-instance].clerk.accounts.dev`
  - `.env.example` → same key with a placeholder form

- [x] **2. Confirm the crypto dependency**
  - `pyproject.toml` → change `"pyjwt>=2.13.0"` to `"pyjwt[crypto]>=2.13.0"`
  - `uv sync`
  - verify: `uv run python -c "import jwt; from jwt import PyJWKClient; print('ok')"`

- [x] **3. Create** `backend/core/security.py`
  **Why this file exists.** Every protected route needs the same question
  answered — "is this request carrying a valid Clerk token, and if so who is it?"
  That logic (fetch Clerk's keys, check the signature, check `iss`/`exp`/`nbf`,
  pull the claims) is identical for `/me`, every event route, every itinerary
  route, and it's also needed outside routes (the item-3 webhook verifies Svix
  signatures, and any background job that touches user data). Writing it once in
  `core/security.py` means:
  - one place to get the crypto right, one place to fix it if Clerk changes
  - routes stay thin — they just write `Depends(get_current_claims)` and receive
  a verified `claims` dict, no JWT code in the handler
  - `verify_token` is a plain function with no FastAPI imports, so it's unit-
  testable on its own and reusable from non-HTTP code
  - `core/` is already where cross-cutting infrastructure lives (`config.py`),
  so auth belongs next to it, not inside any one router
  The file has **four things, in this order**: two module-level variables, then
  two functions. Nothing below is nested inside anything above it unless the
  indentation says so.
  **A.** `jwks_client` **— module level (top of file, not inside any function)**
  - `jwks_client = PyJWKClient(settings.CLERK_JWKS_URL)`
  - It's the object that downloads Clerk's public signing keys (the JWKS) and
  caches them. Created once here so every request reuses the same cache instead
  of re-fetching keys from Clerk.
  **B.** `bearer_scheme` **— module level (top of file, right after** `jwks_client`**)**
  - `bearer_scheme = HTTPBearer(auto_error=False)` — imported from
  `fastapi.security`.
  - This is **not** part of `verify_token`. It's a standalone variable that tells
  FastAPI "routes may send an `Authorization: Bearer <token>` header." It's also
  what adds the **Authorize** button to `/docs`.
  - `auto_error=False`: if the header is missing, FastAPI passes `None` to us
  rather than raising its own `403` — so we can return our own `401` with our
  own message. It gets used in **function D**, not here and not in C.
  **C.** `verify_token(token: str) -> dict` **— a plain function**
  - Takes a token *string*, returns the claims *dict*. Knows nothing about HTTP —
  that's deliberate, so it's easy to unit-test and reuse (the item-3 webhook
  will call it too).
  - Inside a `try:` block:
    - `signing_key = jwks_client.get_signing_key_from_jwt(token)` — reads the
    token's header to see which key id signed it, then pulls that public key out
    of the cached JWKS. `signing_key.key` is the actual key object.
    - `claims = jwt.decode(token, signing_key.key, algorithms=["RS256"], issuer=settings.CLERK_ISSUER, options={"verify_aud": False}, leeway=10)` — this one call does the whole check: recompute the signature with the public key (proves Clerk issued it, unaltered), check `exp`/`nbf` against
    now, check `iss` equals `CLERK_ISSUER`. Parameters:
      - `token` — the string being verified
      - `signing_key.key` — the public key to verify the signature against
      - `algorithms=["RS256"]` — only accept this algorithm; never trust the
      token's own `alg` field (that's a known attack)
      - `issuer=settings.CLERK_ISSUER` — reject any token whose `iss` isn't our
      Clerk instance
      - `options={"verify_aud": False}` — Clerk's default token has no `aud`
      claim, so don't require one
      - `leeway=10` — (default is 0) allows for 10 seconds of clock skew between the token's creation time and current time. If your dev machine's clock is even a couple seconds behind Clerk's, a **freshly minted valid token** can fail with `ImmatureSignatureError` (nbf in the "future") or a near-expiry token can fail early. Standard mitigation is a small `leeway` which is 10 seconds
    - `return claims` — **this is what the function returns**: the decoded payload
    dict (`sub`, `iss`, `exp`, …). You can also write `return jwt.decode(...)`
    directly; same result.
  - `except jwt.PyJWTError:` — one catch covers every failure (bad signature,
  expired, wrong issuer, malformed). In it: `raise HTTPException(401, "Invalid or expired token")`.
  Note it **raises**, it doesn't `return` an error — FastAPI turns the raise
  into the 401 response.
  **D.** `get_current_claims(creds = Depends(bearer_scheme)) -> dict` **— the dependency**
  - A separate function. This is the one routes attach with `Depends(...)`.
  - The parameter `creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)`
  is where `bearer_scheme` from **B** is finally used — FastAPI runs it to pull
  the header off the request and fills in `creds` (or `None` if absent).
  - Body:
    - `if creds is None:` → `raise HTTPException(401, "Missing bearer token")`
    - otherwise → `return verify_token(creds.credentials)`. `creds.credentials`
    is the raw token string (everything after `"Bearer "`).
  - **What it returns**: the claims dict from `verify_token`. FastAPI passes that
  dict into the route as whatever argument declared `Depends(get_current_claims)`.

- [x] **4. Add a temporary probe endpoint**
  - `routers/auth.py` → `GET /auth/whoami` with `claims: dict = Depends(get_current_claims)`, returns `claims`
  - throwaway — item 2 replaces it with the real `GET /me`

- [x] **5. Test**
  - [x] no token → `curl http://localhost:8000/api/v1/auth/whoami` → `401`
  - [x] bad token → `-H "Authorization: Bearer garbage"` → `401`
  - [x] valid token → real token from frontend `getToken()`, or Clerk Dashboard →
    ```
    Sessions, or a JWT template's testing tab → `200` with `sub`, `iss`, `exp`
    ```
  - [x] expired token → wait out a short-lived token (~60s) → `401`
  - [x] `/` and `/docs` still work with no token (dependency wasn't globalized)

- [x] **6. Close out**
  - [x] tick item 1 in `README.md` and `../backend-functionalities.md`
  - [x] note deferred: `azp`/`aud` verification, route-wide enforcement (item 4)

---



## `backend/core/security.py` — annotated

Two functions, on purpose:

- `**verify_token(token)**` — pure logic. String in, claims-`dict` out. Knows
nothing about HTTP or FastAPI, so it's trivial to unit-test and it gets reused
later (e.g. the Clerk webhook, background jobs).
- `**get_current_claims(...)**` — the FastAPI *dependency*. Its only job is to
pull the token off the incoming request, then hand it to `verify_token`. This
is the one your routes write `Depends(...)` against.

```python
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import settings

# ── module level: runs once when this file is first imported ──────────────────

# Knows how to fetch Clerk's public signing keys (the JWKS) and cache them.
# One instance, reused for every request — so we hit Clerk's key endpoint once,
# not on every API call.
jwks_client = PyJWKClient(settings.CLERK_JWKS_URL)

# Declares the "Authorization: Bearer <token>" header to FastAPI. This is what
# puts the "Authorize" button in /docs.
#   auto_error=False -> if the header is missing, FastAPI hands us None instead
#   of raising its own 403. We want to raise our own 401 with our own message.
bearer_scheme = HTTPBearer(auto_error=False)


# ── plain helper: no FastAPI knowledge ───────────────────────────────────────

def verify_token(token: str) -> dict:
    """Verify a Clerk JWT. Returns the claims (decoded payload) or raises 401."""
    try:
        # A JWT header names which key signed it (its "kid"). This looks at the
        # token's header, finds the matching public key in the cached JWKS, and
        # returns it. `signing_key.key` is the actual RSA public key object.
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # The core check. jwt.decode() does ALL of this and raises on any failure:
        #   1. recomputes the signature with `signing_key.key` and compares it
        #      -> proves Clerk really issued this token and nobody altered it
        #   2. checks `exp` (expired?) and `nbf` (used too early?) against now
        #   3. checks `iss` matches `issuer=` below
        # On success it returns the payload as a dict.
        claims = jwt.decode(
            token,
            signing_key.key,               # public key used to verify the signature
            algorithms=["RS256"],          # only accept RS256; never trust the token's own "alg" field
            issuer=settings.CLERK_ISSUER,  # reject tokens whose "iss" != our Clerk instance
            options={"verify_aud": False}, # Clerk's default session token has no "aud" claim, so don't require one
        )
        return claims  # <-- THIS is what the function returns: the claims dict

    except jwt.PyJWTError:
        # Base class for every PyJWT failure: bad signature, ExpiredSignatureError,
        # InvalidIssuerError, DecodeError (malformed), etc. One catch covers all.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── the FastAPI dependency: this is the one routes depend on ──────────────────

def get_current_claims(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """
    Runs before any route that declares `Depends(get_current_claims)`.
    FastAPI fills in `creds` from the Authorization header (or None if absent).
    Whatever this returns becomes the `claims` argument in the route.
    """
    if creds is None:                      # header was missing entirely
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    # creds.credentials == the raw token string after the word "Bearer "
    return verify_token(creds.credentials)  # <-- returns the claims dict to the route
```



### What returns what


| Thing                  | Returns                                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------------------------- |
| `jwt.decode(...)`      | the token payload as a `dict` (the "claims")                                                                  |
| `verify_token()`       | that same `dict` on success; **raises** `HTTPException(401)` on any failure — it never returns an error value |
| `get_current_claims()` | the `dict` from `verify_token`; raises `401` if the header was missing                                        |
| the route (`whoami`)   | receives that `dict` as its `claims` parameter, already verified                                              |


`bearer_scheme` is **not** used inside `verify_token` — it only appears in
`get_current_claims`, as the thing that extracts the header. `verify_token` just
takes a plain string.

---



## Files touched


| File                                    | Change                                                      |
| --------------------------------------- | ----------------------------------------------------------- |
| `backend/core/config.py`                | add `CLERK_ISSUER`                                          |
| `backend/.env` / `backend/.env.example` | add `CLERK_ISSUER`                                          |
| `backend/pyproject.toml`                | `pyjwt` → `pyjwt[crypto]`                                   |
| `backend/core/security.py`              | **new** — JWKS client, `verify_token`, `get_current_claims` |
| `backend/routers/auth.py`               | temporary `GET /auth/whoami` probe                          |




## Deferred / follow-ups

- Verify `azp` (authorized parties) or `aud` once a Clerk JWT template is set up.
- Drop `python-jose` from dependencies once nothing uses it.
- Route-wide auth enforcement → Phase 1 item 4.

