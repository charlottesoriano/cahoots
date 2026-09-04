# Tech Stack — Cahoots (Collaborative Event Planner)

## Frontend — Mobile
- **React Native (Expo)** — cross-platform iOS/Android
- **Expo Router** — file-based navigation
- **Zustand or React Query** — client/server state management, optimistic updates
- **react-native-maps** — itinerary stop visualization
- **Expo Notifications** — push notifications (poll closing, new expense, etc.)
- **NativeWind (Tailwind for RN)** — styling

## Backend
- **Python 3.11+ / FastAPI** — REST API layer
- **Pydantic v2** — request/response validation
- **WebSockets (FastAPI native) or Supabase Realtime** — live sync for polls, presence, itinerary edits
- **Celery + Redis (optional)** — background jobs for notification triggers, reminders
- **Uvicorn/Gunicorn** — ASGI server

## Database & ORM
- **Supabase (Postgres)** — hosted DB, Realtime channels, Storage (for images/docs)
- **Prisma** (Python via Prisma Client Python, or use SQLAlchemy/SQLModel if preferred) — schema modeling, migrations
- **Row Level Security (RLS)** in Supabase — enforce event-membership access at the DB layer

## Auth
- **Clerk** or **Supabase Auth** — session management, invite-link based signup
- **OAuth (Google, Apple)** — low-friction signup
- **JWT** — passed to FastAPI, validated per-request against Clerk/Supabase public keys

## Payments (optional stretch)
- **Stripe (test mode)** — settle-up flow for expense splitting

## Infra / DevOps
- **Docker** — containerize FastAPI backend
- **Railway / Render / Fly.io** — backend hosting (free/cheap tiers)
- **EAS Build (Expo Application Services)** — mobile app builds/distribution
- **GitHub Actions** — CI (lint, test, build) — good portfolio signal

## Testing
- **Pytest** — backend unit/integration tests
- **Jest + React Native Testing Library** — frontend component tests

## Observability (nice-to-have)
- **Sentry** — error tracking on both frontend and backend
