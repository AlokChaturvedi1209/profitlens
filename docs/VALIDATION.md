# Verification and honest handover status

## Tests run in project creation environment

- ✅ `cd backend && pytest -q` — **10 passed**.
- ✅ Exercised authentication, JWT-like signed session token, user isolation, CSV imports, duplicate imports, financial math, rollback on invalid CSV, read-only demo, seeded analytics, and alert deduplication.
- ✅ Deterministic demo generator creates 3,000+ order attempts over 120 days with returns, intentionally higher risk for selected products, and an engineered recent revenue slowdown.
- ✅ Backend source validated by successful Python test collection and API calls using FastAPI TestClient.
- ⚠️ Frontend `npm install` timed out because package downloads were unavailable in the authoring environment. **The Next.js TypeScript build has not yet been run.** `npm run lint` and `npm run build` must be completed locally.
- ⚠️ Docker was not installed in the authoring environment. Actual PostgreSQL/Docker integration and SMTP delivery require local validation.
- ⚠️ OpenAI optional integration was not called with live credentials.

## Local acceptance checklist

1. `docker compose up --build -d` completes, all containers healthy/running.
2. `curl http://localhost:8000/health` returns `{"status":"ok"}`.
3. Browser on `http://localhost:3000` shows populated demo KPI cards and graphs.
4. On Alerts & Insights click **Run anomaly scan**, inspect created risk alerts.
5. Register account, select private workspace and upload sample `products`, then `orders`, then `returns`.
6. Verify private workspace profitability for examples: two shirts, refund ₹1,798, costs ₹600 + shipping ₹75 + fee ₹117 + return shipping ₹80 = contribution profit **−₹872**.
7. Log out and register a second user; ensure the first account's workspace isn't visible/accessible.
8. Navigate all pages and test mobile viewport.
9. Optional SMTP: set credentials in `.env`, restart worker and create an anomalous private-workspace dataset; check mailbox.
10. Optional OpenAI: set key in `.env`, restart API and check assistant results.

## Known scope limitations

- No payment provider/store integration; manual CSV only.
- No background processing for uploaded CSV: max 10k rows per upload.
- One refund event per order, no partial multi-refund workflows.
- Metrics are calculated from eligible orders in the requested timeframe; optimized aggregate materialization is future work for datasets beyond portfolio-scale.
- No hosted SaaS hardening, no password reset, no role-based access control, no user-specific email alert subscriptions.
- No external store sandbox accounts or SMTP account in the deliverable.
