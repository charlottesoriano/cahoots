# Phase 1 — Auth

Goal: an authenticated CRUD API — every route below Phase 1 sits behind an auth dependency.

## Checklist

- [x] Integrate Clerk (or Supabase Auth) JWT verification middleware
- [x] `GET /me` — return current authenticated user's profile
- [x] Sync webhook: when a user signs up via Clerk, create a corresponding `users` row in Postgres
- [x] Protect all routes below with an auth dependency (`Depends(get_current_user)`)

## Notes

- `users.id` is **not** app-generated — it comes from Clerk/Supabase Auth. The sync
webhook is what inserts the `users` row, passing that external id in. See
`[../phase-0/database-setup-walkthrough.md](../phase-0/database-setup-walkthrough.md)`.
- Relevant settings already stubbed in `backend/core/config.py`: `CLERK_PUBLISHABLE_KEY`,
`CLERK_SECRET_KEY`, `CLERK_JWKS_URL`.

