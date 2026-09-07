# Database Schema — Cahoots

Table structures grouped by functionality. Written in a Postgres-flavored pseudo-DDL — adapt directly to Prisma schema syntax or SQLAlchemy/SQLModel models.

---

## Build checklist

Check off each table as you create it (build order matches the backend phases).

- [x] `users`
- [x] `events`
- [x] `event_members`
- [x] `event_invites`
- [x] `itinerary_items`
- [x] `itinerary_comments` (optional/Phase 2)
- [x] `expenses`
- [x] `expense_shares`
- [x] `polls`
- [x] `poll_options`
- [x] `poll_votes`
- [x] `availability_slots` (Phase 2)
- [x] `packing_items` (Phase 3, optional)
- [x] `notification_log` (optional)

---



## Users



### `users`


| Column       | Type           | Notes                               |
| ------------ | -------------- | ----------------------------------- |
| id           | uuid, PK       | matches Clerk/Supabase Auth user id |
| email        | text, unique   |                                     |
| display_name | text           |                                     |
| avatar_url   | text, nullable |                                     |
| push_token   | text, nullable | Expo push token                     |
| created_at   | timestamptz    | default now()                       |


---



## Events



### `events`


| Column          | Type                | Notes                 |
| --------------- | ------------------- | --------------------- |
| id              | uuid, PK            |                       |
| title           | text                |                       |
| description     | text, nullable      |                       |
| location        | text, nullable      |                       |
| start_date      | date, nullable      |                       |
| end_date        | date, nullable      |                       |
| cover_image_url | text, nullable      | Supabase Storage path |
| created_by      | uuid, FK → users.id |                       |
| created_at      | timestamptz         | default now()         |




### `event_members`


| Column    | Type                      | Notes         |
| --------- | ------------------------- | ------------- |
| id        | uuid, PK                  |               |
| event_id  | uuid, FK → events.id      |               |
| user_id   | uuid, FK → users.id       |               |
| role      | enum('organizer','guest') |               |
| joined_at | timestamptz               | default now() |


> Unique constraint on (`event_id`, `user_id`) — a user can only be a member once per event.



### `event_invites`


| Column     | Type                  | Notes               |
| ---------- | --------------------- | ------------------- |
| id         | uuid, PK              |                     |
| event_id   | uuid, FK → events.id  |                     |
| token      | text, unique          | random invite token |
| created_by | uuid, FK → users.id   |                     |
| expires_at | timestamptz, nullable |                     |
| created_at | timestamptz           | default now()       |


---



## Itinerary



### `itinerary_items`


| Column      | Type                  | Notes                              |
| ----------- | --------------------- | ---------------------------------- |
| id          | uuid, PK              |                                    |
| event_id    | uuid, FK → events.id  |                                    |
| title       | text                  |                                    |
| description | text, nullable        |                                    |
| location    | text, nullable        |                                    |
| latitude    | float, nullable       | for map view                       |
| longitude   | float, nullable       |                                    |
| day_index   | int                   | which day of the trip (0, 1, 2...) |
| sort_order  | int                   | position within the day            |
| start_time  | timestamptz, nullable |                                    |
| end_time    | timestamptz, nullable |                                    |
| created_by  | uuid, FK → users.id   |                                    |
| created_at  | timestamptz           | default now()                      |




### `itinerary_comments` (optional/Phase 2)


| Column            | Type                          | Notes         |
| ----------------- | ----------------------------- | ------------- |
| id                | uuid, PK                      |               |
| itinerary_item_id | uuid, FK → itinerary_items.id |               |
| user_id           | uuid, FK → users.id           |               |
| content           | text                          |               |
| created_at        | timestamptz                   | default now() |


---



## Expenses



### `expenses`


| Column      | Type                   | Notes                 |
| ----------- | ---------------------- | --------------------- |
| id          | uuid, PK               |                       |
| event_id    | uuid, FK → events.id   |                       |
| paid_by     | uuid, FK → users.id    | who fronted the money |
| amount      | numeric(10,2)          |                       |
| currency    | text                   | default 'USD'         |
| description | text                   |                       |
| split_type  | enum('equal','custom') |                       |
| created_at  | timestamptz            | default now()         |




### `expense_shares`


| Column      | Type                   | Notes               |
| ----------- | ---------------------- | ------------------- |
| id          | uuid, PK               |                     |
| expense_id  | uuid, FK → expenses.id |                     |
| user_id     | uuid, FK → users.id    | who owes this share |
| amount_owed | numeric(10,2)          |                     |


> `settlement` ("who owes who") is **computed on the fly** from `expenses` + `expense_shares` — no dedicated table needed. Keep it as a service function that nets out balances per event.

---



## Polls



### `polls`


| Column     | Type                  | Notes                       |
| ---------- | --------------------- | --------------------------- |
| id         | uuid, PK              |                             |
| event_id   | uuid, FK → events.id  |                             |
| question   | text                  | e.g. "Which weekend works?" |
| status     | enum('open','closed') |                             |
| created_by | uuid, FK → users.id   |                             |
| closes_at  | timestamptz, nullable |                             |
| created_at | timestamptz           | default now()               |




### `poll_options`


| Column  | Type                | Notes             |
| ------- | ------------------- | ----------------- |
| id      | uuid, PK            |                   |
| poll_id | uuid, FK → polls.id |                   |
| label   | text                | e.g. "Sept 12–14" |




### `poll_votes`


| Column         | Type                       | Notes         |
| -------------- | -------------------------- | ------------- |
| id             | uuid, PK                   |               |
| poll_option_id | uuid, FK → poll_options.id |               |
| user_id        | uuid, FK → users.id        |               |
| created_at     | timestamptz                | default now() |


> Unique constraint on (`poll_id`, `user_id`) if only one vote per user per poll is allowed — otherwise enforce at the option level depending on your voting rules.

---



## Availability (Phase 2, When2meet-style)



### `availability_slots`


| Column     | Type                 | Notes                                  |
| ---------- | -------------------- | -------------------------------------- |
| id         | uuid, PK             |                                        |
| event_id   | uuid, FK → events.id |                                        |
| user_id    | uuid, FK → users.id  |                                        |
| date       | date                 |                                        |
| time_block | int                  | e.g. index representing a 30-min block |


---



## Packing List (Phase 3, optional)



### `packing_items`


| Column      | Type                          | Notes              |
| ----------- | ----------------------------- | ------------------ |
| id          | uuid, PK                      |                    |
| event_id    | uuid, FK → events.id          |                    |
| label       | text                          |                    |
| assigned_to | uuid, FK → users.id, nullable | null = shared item |
| is_checked  | boolean                       | default false      |
| created_at  | timestamptz                   | default now()      |


---



## Notifications (log, optional but nice for debugging)



### `notification_log`


| Column   | Type                           | Notes                              |
| -------- | ------------------------------ | ---------------------------------- |
| id       | uuid, PK                       |                                    |
| user_id  | uuid, FK → users.id            |                                    |
| event_id | uuid, FK → events.id, nullable |                                    |
| type     | text                           | e.g. 'new_expense', 'poll_closing' |
| sent_at  | timestamptz                    | default now()                      |


---



## Relationship overview

```
users ──< event_members >── events ──< event_invites
                               │
                               ├──< itinerary_items ──< itinerary_comments
                               ├──< expenses ──< expense_shares
                               ├──< polls ──< poll_options ──< poll_votes
                               ├──< availability_slots
                               └──< packing_items
```



## Notes for implementation

- Every child table scoped to an `event_id` should have a Row Level Security policy in Supabase: user must have a row in `event_members` for that `event_id` to read/write.
- Build tables in the same order as the backend phases (users → events/members → itinerary → expenses → polls) so each phase only needs the tables that already exist.
- If using Prisma, this maps almost 1:1 into `schema.prisma` models — happy to convert this into actual Prisma syntax if that's the ORM you land on.

