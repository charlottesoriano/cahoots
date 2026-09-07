# Phase 6 — Expenses

Goal: shared-expense tracking with "who owes who" settlement. Self-contained; good demo even without realtime.

## Checklist

- [ ] `POST /events/{event_id}/expenses` — add expense (amount, payer, split type)
- [ ] `expense_shares` table — auto-calculated from split type (equal/custom)
- [ ] `GET /events/{event_id}/expenses` — list expenses
- [ ] `GET /events/{event_id}/settlement` — debt-simplification calculation ("who owes who")
- [ ] Unit test the settlement algorithm separately (pure function — good portfolio artifact)

## Tables involved

`expenses` (`amount` numeric(10,2), `currency` default 'USD', `split_type` enum),
`expense_shares` (`amount_owed`). **No settlement table** — it's computed on the fly
by a service function that nets balances per event.
See [`../phase-0/database-schema.md`](../phase-0/database-schema.md).
