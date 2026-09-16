# Phase 5 — Real-time sync

Goal: live updates to connected clients. Layered on once there's something worth syncing.

## Checklist

- [ ] Set up WebSocket endpoint (`/ws/events/{event_id}`) OR wire up a Supabase Realtime channel per event
- [ ] Broadcast itinerary changes to connected clients
- [ ] Broadcast presence (who's currently viewing) — in-memory or Redis-backed connection registry
- [ ] Test with two clients connected simultaneously

## Notes

Reused later by Phase 7 (poll results broadcast on vote).
