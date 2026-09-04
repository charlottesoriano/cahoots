# Backend Functionalities — Cahoots (FastAPI)

A build-order checklist. Each phase is meant to be completable and testable before moving to the next — so you always have a working backend, not a half-finished one.

---

## Phase 0 — Project setup
- [ / ] Init FastAPI project (`main.py`, `/routers`, `/models`, `/schemas`, `/services`)
- [ / ] Set up Pydantic settings (`.env` for DB URL, JWT keys, etc.)
- [ / ] Connect to Supabase Postgres (via Prisma Client Python or SQLModel/SQLAlchemy)
- [ ] Set up Alembic or Prisma migrations
- [ ] Add health check endpoint (`GET /health`)
- [ ] Set up CORS middleware for the React Native app
- [ ] Dockerize the app (`Dockerfile`, `docker-compose.yml` for local Postgres)

## Phase 1 — Auth
- [ ] Integrate Clerk (or Supabase Auth) JWT verification middleware
- [ ] `GET /me` — return current authenticated user's profile
- [ ] Sync webhook: when a user signs up via Clerk, create a corresponding `users` row in Postgres
- [ ] Protect all routes below with auth dependency (`Depends(get_current_user)`)

## Phase 2 — Users & Events (core CRUD)
- [ ] `POST /events` — create event (title, dates, location, cover image)
- [ ] `GET /events` — list events the current user belongs to
- [ ] `GET /events/{event_id}` — event detail
- [ ] `PATCH /events/{event_id}` — edit event (organizer only)
- [ ] `DELETE /events/{event_id}` — delete event (organizer only)
- [ ] `event_members` table + role enforcement (organizer/guest) via dependency/decorator

## Phase 3 — Invites
- [ ] `POST /events/{event_id}/invite` — generate invite token/link
- [ ] `POST /invites/{token}/accept` — join event as guest (auto-creates `event_members` row)
- [ ] Handle "already a member" and "invalid/expired token" edge cases

## Phase 4 — Itinerary
- [ ] `POST /events/{event_id}/itinerary` — add itinerary item
- [ ] `GET /events/{event_id}/itinerary` — list items (ordered)
- [ ] `PATCH /itinerary/{item_id}` — edit item
- [ ] `PATCH /events/{event_id}/itinerary/reorder` — bulk reorder (accepts ordered list of IDs)
- [ ] `DELETE /itinerary/{item_id}`

## Phase 5 — Real-time sync
- [ ] Set up WebSocket endpoint (`/ws/events/{event_id}`) OR wire up Supabase Realtime channel per event
- [ ] Broadcast itinerary changes to connected clients
- [ ] Broadcast presence (who's currently viewing) — simple in-memory or Redis-backed connection registry
- [ ] Test with two clients connected simultaneously

## Phase 6 — Expenses
- [ ] `POST /events/{event_id}/expenses` — add expense (amount, payer, split type)
- [ ] `expense_shares` table — auto-calculated based on split type (equal/custom)
- [ ] `GET /events/{event_id}/expenses` — list expenses
- [ ] `GET /events/{event_id}/settlement` — debt-simplification calculation ("who owes who")
- [ ] Unit test the settlement algorithm separately (good portfolio artifact — pure function, easy to test)

## Phase 7 — Polls
- [ ] `POST /events/{event_id}/polls` — create poll + options
- [ ] `POST /polls/{poll_id}/vote` — cast/change vote
- [ ] `GET /polls/{poll_id}` — poll results (live via WebSocket broadcast on vote)
- [ ] `POST /polls/{poll_id}/close` — close poll (organizer only), optionally auto-apply winning option to event

## Phase 8 — Notifications
- [ ] Store Expo push tokens per user (`POST /me/push-token`)
- [ ] Background task/job: on new expense, new poll, itinerary change → send push notification to relevant members
- [ ] (Optional) Celery + Redis if you want a real task queue instead of FastAPI `BackgroundTasks`

## Phase 9 — Polish & portfolio-readiness
- [ ] Input validation everywhere via Pydantic schemas (no raw dicts)
- [ ] Consistent error responses (custom exception handlers)
- [ ] Row Level Security policies in Supabase as a defense-in-depth layer
- [ ] Pytest suite: at least auth, event CRUD, and settlement logic covered
- [ ] OpenAPI docs cleaned up (`/docs` should look presentable — add descriptions/examples)
- [ ] README: architecture diagram, setup steps, `.env.example`

---

## Suggested build order (if you want a strict sequence)
1. Phase 0 → 1 → 2 (get a working, authenticated CRUD API)
2. Phase 3 (invites) — unlocks multi-user testing
3. Phase 4 (itinerary) — your first "real" feature
4. Phase 6 (expenses) — self-contained, good for a demo even without realtime
5. Phase 5 (realtime) — layer on top once you have something worth syncing
6. Phase 7 (polls) — reuses realtime infra from step 5
7. Phase 8 (notifications) — nice finishing touch
8. Phase 9 — do this continuously, not just at the end
