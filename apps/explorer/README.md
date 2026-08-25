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

## Scripts

- `npm run dev` — Next.js on port 3000
- `npm run build` — production build
- `npm run start` — serve the production build on port 3000
- `npm run lint` — ESLint (`eslint-config-next`). Next.js 16 no longer provides `next lint`.
