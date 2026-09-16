# Phase 7 — Polls

Goal: create polls, vote, live results. Reuses the realtime infra from Phase 5.

## Checklist

- [ ] `POST /events/{event_id}/polls` — create poll + options
- [ ] `POST /polls/{poll_id}/vote` — cast/change vote
- [ ] `GET /polls/{poll_id}` — poll results (live via WebSocket broadcast on vote)
- [ ] `POST /polls/{poll_id}/close` — close poll (organizer only), optionally auto-apply winning option to event

## Tables involved

`polls` (`status` enum open/closed, nullable `closes_at`), `poll_options`, `poll_votes`.
Consider a unique constraint on `(poll_id, user_id)` if one vote per user per poll.
See [`../phase-0/database-schema.md`](../phase-0/database-schema.md).
