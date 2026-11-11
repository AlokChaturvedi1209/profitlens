# ProfitLens Architecture

## Data entities

- `users`: account identities with salted PBKDF2 hashes.
- `workspaces`: one demo workspace plus one private workspace per registered user.
- `products`: unique SKU within workspace, with current price, cost, stock and category.
- `orders`: unique external order ID per workspace, with a frozen historical unit price/cost.
- `returns`: one return event per order, with refund value, reason, reverse shipping and restockability.
- `alerts`: deduplicated anomaly notifications, acknowledgment status, and creation timestamp.

Ownership boundaries are enforced by checking `workspace.owner_id` for every private workspace operation; the public demo is read-only. All API data query statements filter by `workspace_id`.

## Execution

- Website: `frontend/app/page.tsx` client-side dashboard using Next.js App Router and `lib/api.ts` typed REST calls. Responsive styles in `app/globals.css`.
- API: `backend/app/main.py` owns authentication, pagination, imports, assistant and analytic routes.
- DB and credentials: `backend/app/core.py`.
- Metrics and anomalies: `backend/app/analytics.py`.
- Sample generator: `backend/app/seed.py`; deterministic seeded demo avoids external dependency.
- Monitoring process: `backend/app/worker.py` scans every configured interval, designed to run as its own container.
- Notifications: `backend/app/mailer.py`; logs failures without revealing credentials.

## Important design choices

- SQLite is development fallback; Docker PostgreSQL is the intended stack.
- Fixed historical price/cost values on order prevent product catalog edits from altering past revenue.
- CSV import validates before completing its transaction; bad rows roll back the whole import.
- SMTP optional and not required for running demo.
- Assistant offers deterministic answers when external AI service is unavailable.
- Demo is public/read-only; private workspaces require user authentication.
