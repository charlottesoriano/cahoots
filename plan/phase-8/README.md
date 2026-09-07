# Phase 8 — Notifications

Goal: push notifications to relevant members on key events. Nice finishing touch.

## Checklist

- [ ] Store Expo push tokens per user (`POST /me/push-token`)
- [ ] Background task/job: on new expense, new poll, itinerary change -> push to relevant members
- [ ] (Optional) Celery + Redis if you want a real task queue instead of FastAPI `BackgroundTasks`

## Tables involved

`users.push_token`, `notification_log` (optional, for debugging).
Setting already stubbed: `EXPO_ACCESS_TOKEN` in `backend/core/config.py`.
