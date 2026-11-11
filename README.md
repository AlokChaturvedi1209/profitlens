# ProfitLens — E-commerce Profitability & Returns Intelligence

**ProfitLens** is an end-to-end, full-stack commerce analytics website. It offers a polished Next.js dashboard, a Python/FastAPI REST API, PostgreSQL persistence, realistic seeded demo data, private user workspaces, CSV imports, profit and refunds accounting, operational anomaly alerts, and an optional OpenAI-backed analytics assistant.

> **Project status:** Backend tested (10 passing automated tests). Frontend source is complete, but `npm install` timed out in the build environment, so a Next.js production build and Docker integration were **not verified here**. Docker was unavailable. Follow the local checklist below before claiming the deployment is fully operational.

## Included functionality

| Feature | Notes |
| --- | --- |
| Demo workspace | Deterministic ~3,000 simulated orders; publicly viewable, read-only |
| Private workspaces | Account sign-up, sign-in, HMAC-authenticated expiring sessions, per-user data boundaries |
| Executive overview | Revenue, profit, return rate, margins, sales trend, categories, top products |
| Sales analytics | Paginated orders, product breakdown, downloadable metrics report |
| Product profitability | Revenue − refunds − COGS − shipping − platform fees − return shipping |
| Returns/refunds | Reason analysis, risky products, order-level refunds |
| Inventory | Per-SKU prices, stock count and low-stock indicators |
| Alerts | High return rates, negative product contribution, short-term revenue drops; deduplication |
| Scheduled monitoring | Separate Python worker, 15-minute scan cadence by default |
| Email notifications | Optional SMTP, only for *new* private workspace alerts |
| Assistant | Works out of the box with accurate rule-based metric summaries; optional OpenAI mode |
| Data upload | CSV import with size, column, datatype, key, and foreign-key validations |
| Sample datasets | Templates in `samples/` and within website at `/samples/*.csv` |

## Quickstart: Windows/macOS/Linux with Docker

1. Install **Docker Desktop** and start it. Make sure ports `3000`, `8000`, and `5436` are available.
2. Unzip the project and open a terminal in its `profitlens/` directory.
3. Copy the env template: `cp .env.example .env` on macOS/Linux, or `Copy-Item .env.example .env` in PowerShell.
4. **Change** `APP_SECRET` to a long random secret before using accounts. For local-only development the default postgres password in `.env.example` is a convenience; change it for deployed environments.
5. Run `docker compose up --build -d`.
6. Visit **http://localhost:3000** for the website, and **http://localhost:8000/docs** for Swagger API docs.
7. Select the preloaded demo, explore analytics, click **Run anomaly scan** in Alerts & Insights. To upload your own data, sign up, choose **My Workspace**, and import `products.csv` → `orders.csv` → `returns.csv`.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs -f api
docker compose down
```

### Local developer mode (without Docker)

The backend supports SQLite for development. From `backend/`:

```bash
python -m venv .venv
# Activate .venv for your OS
pip install -r requirements.txt
# No DATABASE_URL => local ./profitlens.db
uvicorn app.main:app --reload --port 8000
```

From `frontend/` in a separate terminal:

```bash
npm install
npm run dev
```

Optional monitoring: in the `backend/` directory, run `python -m app.worker`. In the Docker compose environment, the worker is started separately.

### Tests

```bash
cd backend
pip install -r requirements.txt pytest
pytest -q
```

Frontend validation: `cd frontend && npm install && npm run lint && npm run build`. Docker integration: `docker compose up --build -d`, then `curl http://localhost:8000/health` and open `http://localhost:3000`.

## Website navigation

1. **Overview** — KPIs and revenue/profit charts.
2. **Sales Analytics** — order table with pagination and category breakdown.
3. **Profitability** — product contribution profit and cost explanation.
4. **Returns & Refunds** — return reasons, refund values, and risky SKUs.
5. **Inventory** — remaining stock and low-stock thresholds.
6. **Alerts & Insights** — monitor anomalies, manually scan, acknowledge private-workspace alerts.
7. **Import Data** — upload validated CSV data.
8. **AI Assistant** — ask grounded questions about your data.
9. **Settings** — account info and workspace context.

## CSV schemas (required column names)

- **products.csv**: `sku,name,category,cost,price,stock`
- **orders.csv**: `external_id,sku,purchased_at,quantity,unit_price,unit_cost,shipping,platform_fee,status`
- **returns.csv**: `external_id,order_external_id,reason,refunded_amount,return_shipping,restockable`

`purchased_at` uses ISO-8601. Statuses: `delivered`, `processing`, `shipped`, `cancelled`. Cancelled orders are excluded from revenue analytics. One return per order is supported in V1. Use INR denominated numbers, nonnegative costs, prices, and fees; integer stock and quantity. Max 2 MB / 10,000 rows per upload. Duplicate keys in the same workspace are skipped.

## Financial definitions

**Gross revenue** = Σ(quantity × unit price) for non-cancelled orders.

**Net revenue** = Gross revenue − refunded amounts.

**Contribution profit** = Net revenue − product cost of goods − outbound shipping − marketplace/platform fees − return shipping.

**Margin** = Contribution profit ÷ Net revenue × 100 (0 if no net revenue).

**Return rate** = Returned orders ÷ eligible orders × 100.

**Average order value** = Gross revenue ÷ eligible orders.

Cost of returned products is not automatically recovered, even if marked restockable. Fixed overhead, taxes, fulfillment charges outside fields, and ads are not included. Profit shown is *contribution profit*, not GAAP net income. Revenue is by order date, refunds attached to the original order's period rather than refund-event date. The overview filters are relative to current UTC date.

## Alert rules

- Return risk: at least 8 orders in the past 30 days and ≥ 20% return rate for one SKU.
- Negative contribution: at least 5 orders and profit below ₹0 in the past 30 days.
- Revenue decline: last 3 **completed** daily averages below 55% of the preceding 11-day average, with baseline ≥ ₹1,000.
- Alerts are stored uniquely by key to avoid repeated emails; revenue drops are keyed by end-of-window date. Old alerts remain as historical events; acknowledgment is manual.
- Email requires `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (optional, defaults to user), `ALERT_TO_EMAIL`. StartTLS on port 587, SSL on port 465.
- Scanner runs periodically via `monitor`; demo alerts never send email.

## AI Assistant

Without `OPENAI_API_KEY`, it generates trusted responses about store KPIs, profitability, top products, and returns. With the key, it can use the OpenAI chat completions API for broader narrative answers grounded in a bounded **aggregate snapshot** (not all raw orders). If the external call fails, it falls back to local deterministic answers. Set `OPENAI_MODEL` to a model available in your OpenAI account. Only use with data you are permitted to send to a third party.

## Architecture

```text
Browser -> Next.js 15 / React 19 / Recharts / Tailwind-free custom CSS
              |
              | REST + bearer token
              v
          FastAPI (Python)
              |
              +-- SQLAlchemy -> PostgreSQL (Docker) / SQLite (local)
              +-- CSV validation and import
              +-- Analytics and financial measures
              +-- Anomaly engine -> Alerts table
              +-- Optional OpenAI API
              |
       Standalone monitor worker -> SMTP notifications
```

## Repository layout

```text
profitlens/
├── frontend/         Next.js website, Recharts, responsive CSS, CSV examples
├── backend/app/      FastAPI application, models, analytics, seed, worker, mail
├── backend/tests/    Automated tests
├── docs/             Architecture, validation, known limitations
├── samples/          Import templates
├── compose.yaml      PostgreSQL, API, monitor, website
├── .env.example      Settings template (no real secrets)
└── README.md
```

## Security and deployment notes

This is a **portfolio-grade local project**, not a security-reviewed production SaaS. The demo data is fictional. Never commit `.env`. The browser currently stores bearer tokens in `localStorage`; for an internet-exposed service, switch to secure HttpOnly cookie sessions and add CSRF protection where appropriate. Add authentication rate limiting, per-user alert destinations, password reset / email verification, migrations, backups, HTTPS, audit logging, and a production task queue before using with sensitive customers. The CSV limit is enforced; additional upload scanning and field validation may be needed for wider production use. The API is bound to localhost via Docker port mapping; adjust reverse proxy setup for hosted use.

Troubleshooting: See `docs/VALIDATION.md` for verification status and integration checklist.
