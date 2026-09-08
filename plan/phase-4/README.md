# Phase 4 — Itinerary

Goal: the first "real" feature — day-by-day itinerary items, ordered.

## Checklist

- [ ] `POST /events/{event_id}/itinerary` — add itinerary item
- [ ] `GET /events/{event_id}/itinerary` — list items (ordered by `day_index`, then `sort_order`)
- [ ] `PATCH /itinerary/{item_id}` — edit item
- [ ] `PATCH /events/{event_id}/itinerary/reorder` — bulk reorder (accepts ordered list of IDs)
- [ ] `DELETE /itinerary/{item_id}`

## Tables involved

`itinerary_items` (`day_index`, `sort_order`, optional `latitude`/`longitude` for map view),
`itinerary_comments` (optional). See [`../phase-0/database-schema.md`](../phase-0/database-schema.md).
