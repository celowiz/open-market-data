# Open Market Data Explorer

Read-only Next.js App Router UI for the public FastAPI (`/v1` only). It never
connects to PostgreSQL and never calls CVM or B3 from the browser.

## Run locally

1. Copy `.env.local.example` to `.env.local` (optional; the default API base is
   `http://127.0.0.1:8000`).
2. Start FastAPI with CORS allowing `http://localhost:3000`:

   ```bash
   uv run uvicorn marketdata.api.main:app --reload --host 127.0.0.1 --port 8000
   ```

3. In this directory:

   ```bash
   npm install
   npm run dev
   ```

   Open [http://localhost:3000](http://localhost:3000).

Charts stay empty until historical backfill has populated PostgreSQL. A 404 is
shown as the API error body; prices are never invented.

## Production (Vercel)

The public Explorer is [https://open-market-data.vercel.app/](https://open-market-data.vercel.app/).
It fetches `{NEXT_PUBLIC_API_BASE_URL}/v1/...` in the browser. Production
points at `https://api-production-288d4.up.railway.app` (no trailing slash).
Without that variable, the build defaults to `http://127.0.0.1:8000`, which
visitors cannot reach.

Do **not** set Python `PUBLIC_*` variables on this Vercel project
(`PUBLIC_DATA_BASE_URL` is a FastAPI/CDN setting). The only Explorer env var
is `NEXT_PUBLIC_API_BASE_URL`, with Vercel visibility **config** (not secret).
Redeploy after changing it. Never put a database URL on Vercel.

Public `/v1` is Railway FastAPI (ADR-0005). Remaining operator work is Neon
historical backfill, not provisioning Railway. See
[`docs/DEPLOYMENT.md`](../../docs/DEPLOYMENT.md#remaining-operator-work-historical-backfill-into-neon).
Local `npm run dev` still targets local uvicorn by default.

## Scripts

- `npm run dev` — Next.js on port 3000
- `npm run build` — production build
- `npm run start` — serve the production build on port 3000
- `npm run lint` — ESLint (`eslint-config-next`). Next.js 16 no longer provides `next lint`.
