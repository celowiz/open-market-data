# Deployment

Phase 11 artifacts: a portable API `Dockerfile`, GitHub Actions ingest/publish
workflows, and this runbook.

Official hosting is an operator step with explicit approval. Local development
must keep working with PostgreSQL and `./data` only. Agents must not create
paid resources unless the user asks in the same session.

Current operator state (2026-08-24):

- **Neon** is the serving-database target. Populate it with Phase 12
  `marketdata backfill` **before** hosting FastAPI.
- **Vercel** Data Explorer is live at
  [https://open-market-data.vercel.app/](https://open-market-data.vercel.app/).
  It talks only to FastAPI `/v1` — never to `DATABASE_URL`. Until a public
  API exists it defaults to `http://127.0.0.1:8000` (the visitor's machine).
- **Railway** FastAPI is **not** created yet. Do not provision it until Neon
  serving tables have history. Then follow
  [Next operator step: Railway FastAPI](#next-operator-step-railway-fastapi-after-neon-backfill).
- Cloudflare R2 is not enabled.

Cron conversion and B3 trading-date rules live in
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

### $0 scratch universe (opt-in)

Default B3 ingest still persists the **full** BVBG.186 LAST file. For a cheap
scratch database (Neon Free), persist only IBOV+SMLL equities from the
coverage CSV:

```text
# in .env
INGEST_UNIVERSE=scratch
```

`scratch` reads `config/instruments.csv` if present, else
`config/instruments.example.csv`. An explicit
`B3_EQUITY_UNIVERSE_PATH=/path/to/universe.csv` (same columns as the example
file) wins over `INGEST_UNIVERSE`. Tickers outside the B3 equity rows are
skipped, not errored.

Then run B3 (and optionally BCB). CVM dispatch is class-filtered
(`CVM_CLASSES=Multimercado,Ações`); `ingest-cvm.yml` stays dispatch-only.
Tesouro honors `TESOURO_CURRENT_TITLES_ONLY` (default true). Do **not** pass
`--cotahist`. BVBG.187 futures stay on (existing MVP regex; not filtered by
the equity allowlist).

GitHub Actions `ingest-b3.yml`, `ingest-all.yml`, and `backfill.yml` pass
`INGEST_UNIVERSE` (and `B3_EQUITY_UNIVERSE_PATH` when set) from repository
Actions variables. Empty/unset keeps default full BVBG.186 persist.

```bash
uv run marketdata ingest b3 --date YYYY-MM-DD
uv run marketdata ingest bcb --date YYYY-MM-DD
```

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

# 1. Tesouro: one CSV, history since 2002. Default TESOURO_CURRENT_TITLES_ONLY=true
#    keeps currently traded titles only (latest Data Base date, full history of
#    those titles) so Neon Free stays in budget. Set false for the old full CSV.
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

### Tesouro currently traded titles

Daily ingest and backfill persist only titles that appear on the latest
`Data Base` date in the Tesouro Transparente CKAN CSV (on the order of ~58
titles today). Full history of those titles is kept. Rows whose identity is
absent from that latest-day set (matured / off-book) are skipped.

Controlled by `TESOURO_CURRENT_TITLES_ONLY` (default `true`) so the project
fits Neon Free. Set `TESOURO_CURRENT_TITLES_ONLY=false` to restore the old
full-CSV persist (all titles, including matured). This setting is
forward-looking ingest only; it does not delete quotes already stored.

---

## API container

The repository `Dockerfile` is host-agnostic (ADR-0005). It installs the
package with `uv sync --frozen --no-dev` and runs:

```text
uvicorn marketdata.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

It does **not** bake `.env`, credentials, or a default ingest command.
Pass configuration at runtime (`-e`, `--env-file`, or the host's env).

The image copies repository `config/` into `/app/config` (WORKDIR `/app`).
`coverage_config_dir` defaults to `.`, so `GET /v1/coverage?universe=example`
resolves `config/instruments.example.csv` inside the container. The operator
file `config/instruments.csv` is gitignored and is **not** in the image;
`universe=operator` remains 404 until that file is supplied at runtime.

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

## Production shape

Intended official stack. Neon and Vercel exist as operator projects; Railway
is the next hosting step **after** Neon backfill.

| Role | Intended choice | App sees | Operator status |
|---|---|---|---|
| Serving database | Neon PostgreSQL | `DATABASE_URL` | Target for Phase 12 live load |
| API process | Railway, this `Dockerfile` | `PORT` (injected) + env vars below | **Not created** — wait for Neon history |
| Object storage | Cloudflare R2 (S3-compatible), when enabled | `OBJECT_STORAGE_BACKEND=s3` and `OBJECT_STORAGE_*` | R2 not enabled |
| Scheduled ingest | GitHub Actions → project CLI (ADR-0006) | same env via Actions secrets/variables | Workflows exist |
| Data Explorer | Vercel Next.js (Phase 13) | `NEXT_PUBLIC_API_BASE_URL` only — never `DATABASE_URL` | Live at [open-market-data.vercel.app](https://open-market-data.vercel.app/) |

Self-hosters may use any PostgreSQL, any S3-compatible bucket, and the same
image or `uvicorn`. Cloud vendors are deployment choices, not domain
dependencies.

Raw artifacts must survive the process that wrote them. GitHub-hosted runners
are ephemeral: if `OBJECT_STORAGE_BACKEND=local`, objects vanish when the job
ends while PostgreSQL provenance still points at them. Production ingest
should use a durable backend (`s3` or a self-hosted disk that is not the
runner workspace).

---

## Next operator step: Railway FastAPI (after Neon backfill)

**Gate:** do not create a Railway project until `marketdata backfill` has
written the intended history into Neon. Confirm with `/v1` against local
uvicorn pointed at that `DATABASE_URL`, or with SQL against Neon.

The public Explorer cannot call `127.0.0.1:8000`. Any public FastAPI host
would work; Railway is the official choice (ADR-0005). Fly, Render, or a VPS
are valid self-host alternatives, not the official instance.

When the operator explicitly approves this step:

1. Create a Railway service from this repository `Dockerfile`. Railway injects
   `PORT`; the image already binds `0.0.0.0`.
2. Set Railway `DATABASE_URL` to the Neon URL (`postgresql://…?sslmode=require`).
   Suggested release command: `alembic upgrade head`.
3. Set Railway `CORS_ALLOWED_ORIGINS` to the exact Explorer origins:

   ```text
   CORS_ALLOWED_ORIGINS=https://open-market-data.vercel.app,http://localhost:3000
   ```

   No trailing slash on origins.
4. Set Railway `PUBLIC_API_BASE_URL` to the Railway public origin (no path).
   Other Python `PUBLIC_*` names (`PUBLIC_DATA_BASE_URL`,
   `PUBLIC_DATASET_PUBLICATION_ENABLED`, `PUBLIC_DATASET_FORMAT`) stay on
   FastAPI / GitHub Actions. **Do not add them to the Vercel project** and
   **do not rename them** in `.env.example` to dodge the Vercel dashboard.
5. On the Vercel Explorer project, set **only**:

   | Name | Value | Visibility |
   |---|---|---|
   | `NEXT_PUBLIC_API_BASE_URL` | `https://<railway-public-host>` (no trailing slash) | **config**, not secret |

   Vercel treats `NEXT_PUBLIC_`, `PUBLIC_`, and `VITE_` as public framework
   prefixes. Those variables cannot use `visibility: secret` because they are
   inlined into the browser bundle. After saving, **redeploy** so the build
   picks up the value.
6. Do **not** put `DATABASE_URL` on Vercel.
7. Smoke tests: `GET https://<railway>/v1/health` then open
   [https://open-market-data.vercel.app/](https://open-market-data.vercel.app/)
   and confirm example cards hit `/v1` (404 body from the API is fine; a
   connection error to `127.0.0.1:8000` is not).

Local `.env` may set `YAHOO_PROVIDER_ENABLED=true` for development. Keep
`.env.example` at `false`. Production Yahoo on Railway is a separate flag
decision (ADR-0013); it is not required to wire Explorer → FastAPI.

---

## Environment variable ownership

Python settings in [`.env.example`](../.env.example) belong on FastAPI
(local, Railway) and on GitHub Actions ingest jobs. They are **not** Next.js
variables.

| Variable | Where | Notes |
|---|---|---|
| `DATABASE_URL` | FastAPI, GitHub Actions | Never Vercel |
| `CORS_ALLOWED_ORIGINS` | FastAPI | Include the Vercel origin when the API is public |
| `PUBLIC_API_BASE_URL` | FastAPI | Canonical public URL of this API |
| `PUBLIC_DATA_BASE_URL` | FastAPI / Actions | Parquet/CDN base for manifests; not the Explorer |
| `PUBLIC_DATASET_*` | FastAPI / Actions | Publication gate; not the Explorer |
| `NEXT_PUBLIC_API_BASE_URL` | Vercel / `apps/explorer/.env.local` | Browser fetch target for `/v1`. Default `http://127.0.0.1:8000` |
| `YAHOO_PROVIDER_ENABLED` | FastAPI `.env` | `.env.example` stays `false`; local `.env` may be `true` |

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
| `INGEST_UNIVERSE` | empty (full BVBG.186). `scratch` = coverage CSV |
| `B3_EQUITY_UNIVERSE_PATH` | empty. Explicit CSV wins over `INGEST_UNIVERSE` |
| `PUBLIC_DATASET_PUBLICATION_ENABLED` | `false` (must be `true` to publish) |
| `PUBLIC_DATASET_FORMAT` | `parquet` |
| `PUBLIC_DATA_BASE_URL` | Public CDN/base URL for dataset manifests |
| `CVM_PROVIDER_ENABLED` | `true` |
| `CVM_CLASSES` | `Multimercado,Ações` (empty in Settings = persist all) |
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
| `DATABASE_POOL_RECYCLE` | `300` (Neon idle timeout; `pool_pre_ping` is always on) |
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
with an error message. They will not scrape public websites into nowhere. Add
it only as a GitHub Actions **secret** (Settings → Secrets and variables →
Actions). Do not commit the value, paste it in docs, or clone-and-push it.
This repository currently has no Actions secrets; scheduled jobs stay red
until that secret exists.

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
| `CVM_CLASSES` | variable | `CVM_CLASSES` | No (CVM jobs default `Multimercado,Ações`) |
| `INGEST_UNIVERSE` | variable | `INGEST_UNIVERSE` | No. Empty = persist full B3 BVBG.186. `scratch` filters 186 LAST to the coverage CSV. Wired on `ingest-b3.yml`, `ingest-all.yml`, and `backfill.yml`. |
| `B3_EQUITY_UNIVERSE_PATH` | variable | `B3_EQUITY_UNIVERSE_PATH` | No. Empty is fine. When set, wins over `INGEST_UNIVERSE`. Same three B3 jobs. |

Do not put secret values in workflow YAML. Do not commit `.env`.

`ingest-cvm.yml` and `ingest-all.yml` are **workflow_dispatch only** (no daily
cron). CVM persist is filtered by `CVM_CLASSES`. Daily scheduled ingest is the
per-provider crons (BCB, B3, Tesouro). Do not enable an `ingest-all.yml`
schedule together with those crons.

`ingest-yahoo.yml` is **workflow_dispatch only** (no cron). `backfill.yml` is
**workflow_dispatch only** (no daily cron).

`ingest-all.yml` calls `marketdata ingest all` when dispatched. `backfill.yml`
calls `marketdata backfill <provider> --start --end`. GitHub-hosted jobs cap
at 6 hours; a full CVM HIST span should run locally.

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

# public Explorer on Vercel (set on Railway when FastAPI is hosted)
# CORS_ALLOWED_ORIGINS=https://open-market-data.vercel.app,http://localhost:3000
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
