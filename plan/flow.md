# Flow — Cahoots (Collaborative Event Planner)

## 1. Auth flow
1. User opens app → sees Sign In / Sign Up screen
2. User taps "Continue with Google" (OAuth) or enters email/password
3. Clerk/Supabase Auth issues a session + JWT
4. App stores JWT securely (Expo SecureStore)
5. All subsequent API calls to FastAPI include JWT in `Authorization: Bearer <token>` header
6. FastAPI middleware validates JWT against Clerk/Supabase public key before processing request

## 2. Event creation & invite flow
1. Organizer taps "New Event" → fills title, dates, location
2. FastAPI creates `events` row + adds organizer to `event_members` with role=`organizer`
3. Organizer taps "Invite" → app generates a shareable invite link (token tied to event_id)
4. Invitee opens link → if not signed in, routed through auth flow first
5. On successful auth, invitee is auto-added to `event_members` with role=`guest`
6. Invitee is redirected into the event's itinerary screen

## 3. Real-time itinerary editing
1. User opens Itinerary tab → app subscribes to the event's Realtime channel (Supabase Realtime or FastAPI WebSocket)
2. Organizer adds/edits/reorders an itinerary item → PATCH/POST request to FastAPI
3. FastAPI writes to Postgres, then broadcasts the change over the Realtime channel
4. All connected clients receive the update and re-render the itinerary — no manual refresh needed
5. Optimistic UI: the editing client updates its local state immediately, then reconciles with the server broadcast

## 4. Polling flow (date/place voting)
1. Organizer creates a poll (e.g., "Which weekend?") with options
2. Members receive a push notification: "New poll in [Event Name]"
3. Each member taps to vote → vote recorded, broadcast live to all members
4. Poll results update in real time as votes come in
5. Organizer (or auto-timer) closes the poll → winning option can be auto-applied to event dates

## 5. Expense & settlement flow
1. Any member adds an expense (amount, payer, split type: equal/custom)
2. FastAPI creates an `expenses` row + corresponding `expense_shares` rows per member
3. Backend runs a debt-simplification calculation across all expenses in the event
4. "Who owes who" screen shows the minimal set of transactions to settle all debts
5. (Stretch) Member taps "Settle up" → Stripe test-mode payment link generated

## 6. Notification flow
1. Trigger events (new expense, poll closing, itinerary change) are queued as background jobs (Celery or FastAPI BackgroundTasks)
2. Job looks up relevant `event_members` and their push tokens
3. Notification is sent via Expo Push Notification service
4. Tapping the notification deep-links into the relevant screen (e.g., straight to the poll)

## High-level system diagram (describe in README)
```
[React Native App] <--REST/WebSocket--> [FastAPI Backend] <--> [Supabase Postgres + Realtime + Storage]
        |                                       |
   [Expo SecureStore]                     [Clerk/Supabase Auth]
        |                                       |
   [Expo Push Notifications] <-----------[Background Jobs]
```
