# Phase 9 — Polish & portfolio-readiness

Goal: make the API presentable and safe. Do this continuously, not just at the end.

## Checklist

- [ ] Input validation everywhere via Pydantic schemas (no raw dicts)
- [ ] Consistent error responses (custom exception handlers)
- [ ] Row Level Security policies in Supabase as a defense-in-depth layer
- [ ] Pytest suite: at least auth, event CRUD, and settlement logic covered
- [ ] OpenAPI docs cleaned up (`/docs` presentable — descriptions/examples)
- [ ] README: architecture diagram, setup steps, `.env.example`

## RLS notes

Every table is currently `UNRESTRICTED` (RLS off). Before deploy, either enable RLS
with policies keyed on `event_members` (user must have a row for that `event_id` to
read/write), or ensure the Supabase anon key never ships to clients and all access
goes through FastAPI with the secret key.
See the "UNRESTRICTED" section in
[`../phase-0/database-setup-walkthrough.md`](../phase-0/database-setup-walkthrough.md).
