# Open Market Data — Contributing

Code is licensed under Apache-2.0. Data from each source has its own terms;
see `DATA_LICENSES.md` and `docs/LICENSING.md`.

## Setup

Python 3.12+ and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync
cp .env.example .env
```

Set `DATABASE_URL` in `.env` to a local PostgreSQL database when you need
migrations or database tests. Keep
`CORS_ALLOWED_ORIGINS=http://localhost:3000` if you will run the Explorer.
Object storage defaults to `./data` on the filesystem. Neon, Railway, and
Cloudflare are not required for local work. Public FastAPI on Railway waits
until Neon serving tables are backfilled; see `docs/DEPLOYMENT.md`. Optional S3-compatible storage:

```bash
uv sync --extra s3
```

Daily ingest: `uv run marketdata ingest <provider> --date YYYY-MM-DD` or
`uv run marketdata ingest all --date YYYY-MM-DD`.

Historical range ingest (not the daily cron):

```bash
uv run marketdata backfill --help
uv run marketdata backfill tesouro --start 2002-01-01 --end 2026-08-24
```

Do not dump every CVM HIST year in one go. Start with 2025, then widen.
Yahoo is ingestible and currently visible on the public API
(`public_api_enabled=true`). B3 and Yahoo must not be published as Parquet.
Do not commit files under `data/`.

Optional local PostgreSQL:

```bash
docker compose up -d postgres
```

Apply migrations:

```bash
uv run alembic upgrade head
```

### Data Explorer

Node.js 20+ (or current LTS). The app talks only to FastAPI `/v1`.

```bash
uv run uvicorn marketdata.api.main:app --reload --host 127.0.0.1 --port 8000
cd apps/explorer
npm install
npm run dev
```

Open `http://localhost:3000`. Charts need a prior backfill. Never set
`DATABASE_URL` in `apps/explorer`.

## Quality checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Explorer (no secrets):

```bash
cd apps/explorer
npm ci
npm run build
```

The lint script is `eslint` (Next.js 16 does not ship `next lint`).

Format Python:

```bash
uv run ruff format .
```

Unit tests must not call live market-data websites. Tests that need PostgreSQL
are marked `db`. Tests that hit real sources are marked `integration` and are
not required on every commit (`.github/workflows/ci.yml` runs default pytest
only). `backfill.yml` is `workflow_dispatch` only — never add a daily cron.

## Adding a provider

Follow `docs/IMPLEMENTATION_PLAN.md` and later
`docs/contributing/adding-a-provider.md`.

Do not import third-party source clients outside `src/marketdata/providers/`.

## Pull requests

- Keep the change scoped to one phase or one concern.
- Do not commit `.env`, credentials, or files under `data/`.
- Do not add cloud resources or secrets.
- Do not create Neon, Railway, R2, or Vercel projects from a PR.
