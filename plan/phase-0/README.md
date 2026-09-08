# Phase 0 — Project setup

Goal: a running, DB-connected FastAPI skeleton before any feature work.

## Checklist

- [x] Init FastAPI project (`main.py`, `/routers`, `/models`, `/schemas`, `/services`)
- [x] Set up Pydantic settings (`.env` for DB URL, JWT keys, etc.)
- [x] Connect to Supabase Postgres (via SQLModel/SQLAlchemy)
- [x] Set up Alembic migrations
- [x] Add health check endpoint (`GET /health`) — note: for improvement
- [x] Create the database schema (all tables live in Supabase via Alembic)
- [ ] Set up CORS middleware for the React Native app
- [ ] Dockerize the app (`Dockerfile`, `docker-compose.yml` for local Postgres)

## Docs in this folder

| File | What it covers |
|---|---|
| [`database-schema.md`](./database-schema.md) | Table definitions — source of truth for every model |
| [`alembic-setup.md`](./alembic-setup.md) | One-time Alembic wiring: `alembic.ini`, `env.py`, `script.py.mako`, Supabase connection detail |
| [`database-setup-walkthrough.md`](./database-setup-walkthrough.md) | Turning the schema into real tables: model file pattern, the `User` example, registering models, the "Target database is not up to date" error + fix, the `UNRESTRICTED` / RLS note |

## Open follow-ups

- Delete the unused `init_db()` in `backend/database/database.py` (Alembic owns the schema now).
- `backend/main.py`: `AsyncSession` is used at the `/test-db-connection` route but never imported; `select` import is unused.
- RLS is off on every table (`UNRESTRICTED`). Fine for dev — revisit in Phase 9 before deploy.
