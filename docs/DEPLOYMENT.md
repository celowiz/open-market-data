# Deployment

Phase 11 artifacts: a portable API `Dockerfile`, GitHub Actions ingest/publish
workflows, and this runbook.

**This phase does not create Neon, Railway, Cloudflare R2, Vercel, or any other
cloud project.** Official hosting remains an operator step with explicit
approval. Local development must keep working with PostgreSQL and `./data`
only.

Historical population of PostgreSQL (`marketdata backfill`) is **Phase 12**.
The Next.js Data Explorer (Phase 13) talks only to FastAPI `/v1` — never to
`DATABASE_URL`. Cron conversion and B3 trading-date rules live in
[`INGEST_SCHEDULE.md`](INGEST_SCHEDULE.md).

---

## Local (required path)

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), and Docker **only**
for the Compose PostgreSQL service (or any other local Postgres).

```bash
docker compose up -d postgres
cp .env.example .env
```

Set at least:

```text
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/open_market_data
OBJECT_STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=./data
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

Leave `OBJECT_STORAGE_*` S3 fields empty. Do not point local `.env` at
production Neon.

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn marketdata.api.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/v1/health
```

Expected body: `{"status":"ok"}`. The health route does not query PostgreSQL;
quotes, series, and funds do.

Daily ingest (one reference date; CVM uses a monthly ZIP window):

```bash
uv run marketdata ingest cvm --date YYYY-MM-DD
uv run marketdata ingest tesouro --date YYYY-MM-DD
uv run marketdata ingest bcb --date YYYY-MM-DD
uv run marketdata ingest b3 --date YYYY-MM-DD
# Yahoo is unofficial / POC (ADR-0013); keep YAHOO_PROVIDER_ENABLED=false
# unless you intend a local-only store.
uv run marketdata ingest yahoo --date YYYY-MM-DD
```

Public ODbL Parquet (never B3/Yahoo bulk files — ADR-0014 / ADR-0013):

```bash
# in .env
PUBLIC_DATASET_PUBLICATION_ENABLED=true
uv run marketdata publish datasets --date YYYY-MM-DD
```

Files land under `data/public/...` on the local filesystem backend.

Do not commit `.env` or anything under `data/`.

---

## Operator backfill playbook (cheap → expensive)

Order matters. Use local PostgreSQL and `OBJECT_STORAGE_BACKEND=local`.
Today's example end date is **2026-08-24**. Do **not** dump every CVM HIST
year; start with 2025. Yahoo will not appear in the Explorer. B3 is never
published as Parquet. `backfill.yml` is `workflow_dispatch` only — prefer
running long ranges on a machine you control.

```bash
docker compose up -d postgres
cp .env.example .env   # DATABASE_URL + CORS_ALLOWED_ORIGINS=http://localhost:3000
uv sync
uv run alembic upgrade head

# 1. Tesouro: one CSV, history since 2002
uv run marketdata backfill tesouro --start 2002-01-01 --end 2026-08-24

# 2. BCB: five series, 10-year chunks
uv run marketdata backfill bcb --start 2000-01-01 --end 2026-08-24

# 3. B3 recent official files (not 20 years of Pesquisa por Pregão)
uv run marketdata backfill b3 --start 2024-01-01 --end 2026-08-24

# 3b. Optional deep equities (COTAHIST ≠ 186)
uv run marketdata backfill b3 --start 2020-01-01 --end 2026-08-24 --cotahist

# 4. CVM: start with one year, then widen; HIST is huge
uv run marketdata backfill cvm --start 2025-01-01 --end 2026-08-24
# uv run marketdata backfill cvm --start 2018-01-01 --end 2026-08-24

# 5. Yahoo local only (will not appear in Explorer)
uv run marketdata backfill yahoo --start 2020-01-01 --end 2026-08-24 --symbol AAPL

# 6. Republish ODbL Parquet from serving DB
# set PUBLIC_DATASET_PUBLICATION_ENABLED=true
uv run marketdata publish datasets --date 2026-08-24
```

Then API + Explorer:

```bash
uv run uvicorn marketdata.api.main:app --reload --host 127.0.0.1 --port 8000
cd apps/explorer && npm install && npm run dev
```

Open `http://localhost:3000`. Confirm charts for Tesouro (`LTN:2029-01-01`),
CDI (`BCB:CDI_DAILY`), a CVM CNPJ (`00017024000153`), and PETR4. The Explorer
must never see `DATABASE_URL`.

Optional S3-compatible backend (no buckets are created here):

```bash
uv sync --extra s3
```

Local filesystem remains the default and needs no AWS credentials.

---

## API container

The repository `Dockerfile` is host-agnostic (ADR-0005). It installs the
package with `uv sync --frozen --no-dev` and runs:

```text
uvicorn marketdata.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

It does **not** bake `.env`, credentials, or a default ingest command.
Pass configuration at runtime (`-e`, `--env-file`, or the host's env).

```bash
docker build -t open-market-data .
docker run --rm -p 8000:8000 \
  -e PORT=8000 \
  -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/open_market_data \
  -e OBJECT_STORAGE_BACKEND=local \
  -e LOCAL_STORAGE_PATH=/app/data \
  open-market-data
```

On Linux, `host.docker.internal` may require `--add-host=host.docker.internal:host-gateway`.
One-off migrations using the same image:

```bash
docker run --rm --env-file .env open-market-data alembic upgrade head
```

(Override the image CMD; `alembic.ini` and `migrations/` are copied in.)

---

## Production shape (not provisioned here)

Intended official stack when an operator later approves paid resources:

| Role | Intended choice | App sees |
|---|---|---|
| Serving database | Neon PostgreSQL | `DATABASE_URL` |
| API process | Railway, this `Dockerfile` | `PORT` (injected) + env vars below |
| Object storage | Cloudflare R2 (S3-compatible), when enabled | `OBJECT_STORAGE_BACKEND=s3` and `OBJECT_STORAGE_*` |
| Scheduled ingest | GitHub Actions → project CLI (ADR-0006) | same env via Actions secrets/variables |
| Data Explorer | Vercel / local Next.js (Phase 13) | `NEXT_PUBLIC_API_BASE_URL` only — never `DATABASE_URL` |

Self-hosters may use any PostgreSQL, any S3-compatible bucket, and the same
image or `uvicorn`. Cloud vendors are deployment choices, not domain
dependencies.

Raw artifacts must survive the process that wrote them. GitHub-hosted runners
are ephemeral: if `OBJECT_STORAGE_BACKEND=local`, objects vanish when the job
ends while PostgreSQL provenance still points at them. Production ingest
should use a durable backend (`s3` or a self-hosted disk that is not the
runner workspace).

---

## Railway environment variables

Copy names from [`.env.example`](../.env.example). Do **not** put Railway
MCP/OAuth tokens in application env. Railway injects `PORT`; the container
CMD uses it and binds `0.0.0.0` (ignore `API_HOST` / `API_PORT` inside the
image).

### Required to serve `/v1` from PostgreSQL

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Neon or other PostgreSQL URL. Use `postgresql://…?sslmode=require` on Neon. |

### Strongly recommended in production

| Variable | Example / notes |
|---|---|
| `APP_ENV` | `production` |
| `LOG_LEVEL` | `INFO` |
| `APP_TIMEZONE` | `America/Sao_Paulo` (persisted timestamps stay UTC) |
| `CORS_ALLOWED_ORIGINS` | Explorer origin, comma-separated. See [CORS](#cors-for-the-data-explorer). |
| `OBJECT_STORAGE_BACKEND` | `s3` when R2 (or other S3 API) is enabled; `local` only with a durable volume |
| `PUBLIC_API_BASE_URL` | Public URL of this FastAPI service |
| `API_DOCS_ENABLED` | `true` or `false` |

### Object storage (S3-compatible / future R2)

Used when `OBJECT_STORAGE_BACKEND=s3`. Leave empty for local filesystem.

| Variable | Notes |
|---|---|
| `OBJECT_STORAGE_ENDPOINT` | Provider endpoint URL |
| `OBJECT_STORAGE_BUCKET` | Bucket name |
| `OBJECT_STORAGE_ACCESS_KEY` | Access key id |
| `OBJECT_STORAGE_SECRET_KEY` | Secret. Store only in the host secret manager |
| `OBJECT_STORAGE_REGION` | Default `auto` (R2) |
| `LOCAL_STORAGE_PATH` | Used when backend is `local` (image default `/app/data`) |

### HTTP client (ingest jobs; unused by a read-only API process)

| Variable | `.env.example` default |
|---|---|
| `HTTP_USER_AGENT` | `open-market-data` |
| `HTTP_TIMEOUT_SECONDS` | `30` |
| `HTTP_MAX_RETRIES` | `3` |

### Ingestion / publication flags

| Variable | `.env.example` default |
|---|---|
| `RECENT_REPROCESS_DAYS` | `90` |
| `INGESTION_MAX_CONCURRENCY` | `4` |
| `PUBLIC_DATASET_PUBLICATION_ENABLED` | `false` (must be `true` to publish) |
| `PUBLIC_DATASET_FORMAT` | `parquet` |
| `PUBLIC_DATA_BASE_URL` | Public CDN/base URL for dataset manifests |
| `CVM_PROVIDER_ENABLED` | `true` |
| `B3_PROVIDER_ENABLED` | `true` |
| `TESOURO_PROVIDER_ENABLED` | `true` |
| `BCB_PROVIDER_ENABLED` | `true` |
| `YAHOO_PROVIDER_ENABLED` | `false` in `.env.example` (POC only) |
| `ANBIMA_PROVIDER_ENABLED` | `false` |

### Pool / API skeleton (defaults exist in code)

| Variable | `.env.example` default |
|---|---|
| `DATABASE_POOL_SIZE` | `5` |
| `DATABASE_MAX_OVERFLOW` | `10` |
| `DATABASE_POOL_TIMEOUT` | `30` |
| `API_V1_PREFIX` | `/v1` |
| `API_HOST` | `127.0.0.1` (local uvicorn only) |
| `API_PORT` | `8000` (local uvicorn only) |

Health check for the host: **`GET /v1/health`**.

Suggested Railway release command (not configured by this repository):
`alembic upgrade head`.

---

## GitHub Actions secrets and variables

Workflows live under `.github/workflows/`. They call the CLI; they do not
download provider files in YAML (ADR-0006). They never log `DATABASE_URL`.

If `DATABASE_URL` is missing, ingest/publish/backfill jobs **fail immediately**
with an error message. They will not scrape public websites into nowhere.

| GitHub name | Type | Application env | Required |
|---|---|---|---|
| `DATABASE_URL` | secret | `DATABASE_URL` | **Yes** for every ingest/publish/backfill job |
| `OBJECT_STORAGE_ACCESS_KEY` | secret | `OBJECT_STORAGE_ACCESS_KEY` | When backend is `s3` |
| `OBJECT_STORAGE_SECRET_KEY` | secret | `OBJECT_STORAGE_SECRET_KEY` | When backend is `s3` |
| `OBJECT_STORAGE_BACKEND` | variable | `OBJECT_STORAGE_BACKEND` | No (workflows default `local`) |
| `OBJECT_STORAGE_ENDPOINT` | variable | `OBJECT_STORAGE_ENDPOINT` | When backend is `s3` |
| `OBJECT_STORAGE_BUCKET` | variable | `OBJECT_STORAGE_BUCKET` | When backend is `s3` |
| `OBJECT_STORAGE_REGION` | variable | `OBJECT_STORAGE_REGION` | No (default `auto`) |
| `LOCAL_STORAGE_PATH` | variable | `LOCAL_STORAGE_PATH` | No (default `./data` on the runner) |
| `PUBLIC_DATASET_PUBLICATION_ENABLED` | variable | `PUBLIC_DATASET_PUBLICATION_ENABLED` | **Yes = `true`** for `publish-datasets.yml` |
| `PUBLIC_DATA_BASE_URL` | variable | `PUBLIC_DATA_BASE_URL` | Recommended when publishing |

Do not put secret values in workflow YAML. Do not commit `.env`.

`ingest-yahoo.yml` is **workflow_dispatch only** (no cron). `backfill.yml` is
**workflow_dispatch only** (no daily cron). Prefer either the per-provider
ingest schedules **or** `ingest-all.yml`, not both.

`ingest-all.yml` calls `marketdata ingest all`. `backfill.yml` calls
`marketdata backfill <provider> --start --end`. GitHub-hosted jobs cap at
6 hours; a full CVM HIST span should run locally.

Optional S3 extra (not required for local filesystem):

```bash
uv sync --extra s3
```

Ingest workflows stay on `uv sync --frozen --no-dev` unless the operator
sets `OBJECT_STORAGE_BACKEND=s3` and installs the extra on that runner.

---

## CORS for the Data Explorer

FastAPI sends CORS headers when a browser Explorer calls `/v1` from another
origin (`apps/explorer` on port 3000 locally).

Set `CORS_ALLOWED_ORIGINS` to a comma-separated list of exact origins:

```text
# local Explorer
CORS_ALLOWED_ORIGINS=http://localhost:3000

# later production Explorer (example — not created in this phase)
# CORS_ALLOWED_ORIGINS=https://explorer.example.com
```

Intended middleware (empty string = no CORS middleware):

- `allow_origins` = the parsed list
- `allow_methods=["GET"]`
- `allow_headers=["*"]`

The Explorer must use `NEXT_PUBLIC_API_BASE_URL` (or the public API URL). It
must never receive `DATABASE_URL`.

---

## Quality / CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) stays the Python
quality gate (`ruff`, `pyright`, `pytest`). Explorer CI is
[`.github/workflows/explorer.yml`](../.github/workflows/explorer.yml)
(`npm ci` + `npm run build` with `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`;
no secrets). Ingest schedules are not part of `ci.yml`.
