# Functionalities — Cahoots (Collaborative Event Planner)

## MVP (build first)
- [ ] User signup/login (OAuth + email)
- [ ] Create an event/trip (title, dates, location, cover image)
- [ ] Invite members via shareable link
- [ ] Role-based permissions: organizer (full edit) vs. guest (comment/vote only)
- [ ] Shared itinerary: add/edit/reorder day-by-day items
- [ ] Expense tracking: add expense, split equally or by custom shares
- [ ] "Who owes who" settlement calculator (debt simplification)
- [ ] Real-time sync: itinerary and expense changes appear live for all members

## Phase 2 — Collaboration polish
- [ ] Date/place polls (create poll, vote, live-updating results)
- [ ] Availability grid (When2meet-style, synced live)
- [ ] Comments/reactions on itinerary items
- [ ] Live presence indicators ("Sarah is viewing this itinerary")
- [ ] Push notifications (poll closing soon, new expense added, itinerary changed)

## Phase 3 — Extras / stretch goals
- [ ] Packing list (shared + per-person checklist)
- [ ] Map view of itinerary stops with pins
- [ ] Offline support with sync-on-reconnect
- [ ] Stripe test-mode integration for actually settling debts
- [ ] Export itinerary as PDF/shareable summary
- [ ] Photo album per event (Supabase Storage)

## Non-functional goals (for portfolio credibility)
- [ ] Input validation & error handling on every endpoint (Pydantic)
- [ ] Row-level security so users can only access events they're members of
- [ ] Basic test coverage (backend unit tests, at least one frontend integration test)
- [ ] CI pipeline that runs tests on push
- [ ] README with architecture diagram + setup instructions
