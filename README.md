# Cahoots

Cahoots is a collaborative event/trip planner — shared itineraries, expense
splitting, polls, and live sync for a group planning something together.

This is a small personal learning project. I'm using it to pick up two
stacks I hadn't worked with professionally before: **Python/FastAPI** on the
backend and **React Native (Expo)** on the frontend. The goal is hands-on
practice, not production polish — expect the scope and structure to evolve
as I learn.

## Stack

- **Backend**: Python, FastAPI, SQLModel, Alembic, Supabase (Postgres),
  Clerk (auth)
- **Frontend** (planned): React Native with Expo
- See [plan/stack.md](plan/stack.md) for the full intended stack and
  [plan/functionalities.md](plan/functionalities.md) for the feature list.

## Project structure

```
backend/    FastAPI app, database models, Alembic migrations
plan/       Design notes, phased build plan, and progress checklists
```

The frontend (Expo/React Native app) hasn't been started yet — the backend
is being built first.

## Backend setup

```bash
cd backend
uv sync
cp .env.example .env   # fill in Supabase/Clerk credentials
uv run alembic upgrade head
uv run uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`, with interactive docs
at `/docs`.

### Running with Docker

```bash
cd backend
docker compose up
```

## Progress

This project is being built in phases — see [plan/](plan/) for the roadmap
and current status of each phase.
