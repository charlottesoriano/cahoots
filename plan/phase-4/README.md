# Phase 4 — Invites

Goal: token-based invite links that let a user join an event as a guest. Unlocks multi-user testing.

## Checklist

- [x] `POST /invites/{event_id}` — generate invite token/link
- [x] `POST /invites/{token}/accept` — join event as guest (auto-creates `event_members` row)
- [x] Handle "already a member" and "invalid/expired token" edge cases

## Tables involved

`event_invites` (has `token` unique, nullable `expires_at`), `event_members`.
See `[../phase-0/database-schema.md](../phase-0/database-schema.md)`.