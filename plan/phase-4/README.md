# Phase 4 — Itinerary

Goal: the first "real" feature — day-by-day itinerary items, ordered.

## Checklist

- [x] `POST /itinerary/create` — add itinerary item
- [x] `GET /itinerary/{event_id}` — list items (ordered by `day_index`, then `sort_order`)
- [x] `PATCH /itinerary/{event_id}/{itinerary_id}` — edit item
- [ ] `PATCH /events/{event_id}/itinerary/reorder` — bulk reorder (accepts ordered list of IDs)
- [x] `DELETE /itinerary/{event_id}/{itinerary_id}`

## Tables involved

`itinerary_items` (`day_index`, `sort_order`, optional `latitude`/`longitude` for map view),
`itinerary_comments` (optional). See `[../phase-0/database-schema.md](../phase-0/database-schema.md)`.