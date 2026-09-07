# Phase 2 — Users & Events (core CRUD)

Goal: create/read/update/delete events, with membership + roles enforced.

## Checklist

- [ ] `POST /events` — create event (title, dates, location, cover image)
- [ ] `GET /events` — list events the current user belongs to
- [ ] `GET /events/{event_id}` — event detail
- [ ] `PATCH /events/{event_id}` — edit event (organizer only)
- [ ] `DELETE /events/{event_id}` — delete event (organizer only)
- [ ] `event_members` table + role enforcement (organizer/guest) via dependency/decorator

## Tables involved

`events`, `event_members` — see [`../phase-0/database-schema.md`](../phase-0/database-schema.md).
`event_members` has a unique constraint on `(event_id, user_id)`.
