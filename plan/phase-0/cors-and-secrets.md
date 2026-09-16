# CORS middleware + secret hygiene

Covers two Phase 0 loose ends:

1. Wiring `CORSMiddleware` to a real allow-list so the Expo app can reach the API.
2. Getting live secrets out of version control.

---

## 1. CORS middleware

### Why it matters here

CORS is a **browser** mechanism. Native iOS/Android builds of the Expo app ignore
it entirely. It still matters for:

- Expo Web / React Native Web during development
- the `/docs` and `/redoc` pages if hit from another origin
- anything hitting the API from a browser later

So this is low-stakes for a pure-native app, but cheap to do correctly and avoids
a confusing wall later.

### The problem with the original setup

```python
allow_origins=["*"], allow_credentials=True
```

Invalid combination. Per the CORS spec a browser rejects a wildcard
`Access-Control-Allow-Origin` when credentials are allowed, and Starlette will not
emit the header at all in that case. It looked configured but effectively wasn't.

### What was changed

**`backend/core/config.py`** — `ALLOWED_ORIGINS` is now a real `list[str]` parsed
from a comma-separated env var:

```python
from typing import Annotated, List
from pydantic_settings import BaseSettings, NoDecode
from pydantic import field_validator

class Settings(BaseSettings):
    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = []

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v
```

Key detail: **`NoDecode`**. `pydantic-settings` tries to `json.loads()` any field
whose type is a collection (`list`, `dict`, `set`) *before* running validators. A
plain `http://a,http://b` string fails JSON parsing with:

```
SettingsError: error parsing value for field "ALLOWED_ORIGINS" from source "DotEnvSettingsSource"
```

`Annotated[List[str], NoDecode]` disables that JSON step so the `mode="before"`
validator receives the raw string and can `.split(",")` it.

Alternatives that also work (not used): store the value as valid JSON in `.env`
(`ALLOWED_ORIGINS=["http://a","http://b"]`), or keep the field a `str` and expose
a `@property` that splits it.

**`backend/main.py`** — middleware now reads the setting, and credentials are off
(Clerk sends a JWT in the `Authorization` header, not a cookie, so credentialed
CORS isn't needed):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

If `allow_credentials` is ever turned back on, `allow_origins` must be an explicit
list — never `["*"]`.

### `.env` values for local dev

```
ALLOWED_ORIGINS=http://localhost:8081,http://localhost:19006
```

- `http://localhost:8081` — Expo / Metro dev server
- `http://localhost:19006` — Expo web (older default port), add if you use it
- `exp://...` URLs are not HTTP origins and do nothing for CORS — harmless to omit

### How to test without a frontend

Start the server (`uv run uvicorn main:app --reload` from `backend/`), then send a
preflight:

```bash
curl -i -X OPTIONS http://localhost:8000/api/v1/ \
  -H "Origin: http://localhost:8081" \
  -H "Access-Control-Request-Method: GET"
```

- allowed origin → response includes `access-control-allow-origin: http://localhost:8081`
- disallowed origin (e.g. `http://evil.test`) → that header is absent

### Also fixed while in `main.py`

- `AsyncSession` was used at the `/test-db-connection` route but never imported —
  now imported from `sqlalchemy.ext.asyncio`.
- unused `from sqlmodel import select` removed.

---

## 2. Secret hygiene

### The problem

`backend/.env` was committed with live credentials: the Supabase database
password, `SUPABASE_SECRET_KEY`, and `CLERK_SECRET_KEY`. `backend/.gitignore`
ignored `.venv` but not `.env`.

Anything committed stays in git history forever — adding the file to `.gitignore`
later stops *future* commits but does not un-leak what's already in history.

### Remediation checklist

- [ ] **Rotate every exposed credential** (the only step that actually closes the
      leak):
  - Supabase → Settings → Database → reset database password (updates
    `DATABASE_URL`)
  - Supabase → Settings → API Keys → roll `SUPABASE_SECRET_KEY`
  - Clerk → API Keys → roll `CLERK_SECRET_KEY`
- [ ] Add `.env` to `backend/.gitignore`
- [ ] `git rm --cached backend/.env` and commit (removes it from the working tree
      of future clones; keeps your local copy)
- [ ] Keep a committed template file with placeholder values only

### Current state (verify before closing this out)

As of writing, `git ls-files` still shows `backend/.env` as tracked and
`backend/.gitignore` does not list `.env` — so the git-side steps above may still
be pending even if the keys were rotated.

The template file is currently `backend/env.example`. Two nits:

- conventionally named `.env.example` (leading dot) so it sits next to `.env`
- it uses `CORS_ORIGINS=...`, but the code reads `ALLOWED_ORIGINS` — pick one name
  and make `env.example`, `.env`, and `config.py` agree

---

## Phase 0 checklist impact

- [x] Set up CORS middleware for the React Native app
- [ ] Dockerize the app — separate doc

Secret hygiene isn't a Phase 0 checklist item but overlaps the Phase 9 line
"README: `.env.example`".
