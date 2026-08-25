# Open Market Data

> Early development / pre-alpha.

Open-source platform for collecting, normalizing, and publishing financial
market data from public and preferably official sources.

The project aims to provide:

- transparent financial market data
- strong source provenance
- a public API
- reusable public datasets when licensing allows
- an extensible provider architecture

Initial focus is the Brazilian financial market.

## Status

Core providers (CVM, Tesouro, BCB, B3 equities and derivatives) ingest **one
reference date** (CVM: a monthly ZIP window) into local filesystem object
storage and PostgreSQL. Historical backfill (`marketdata backfill`) is
**Phase 12**. A Next.js Data Explorer is **Phase 13**.

The public API and bulk datasets are not generally available yet. See
[`docs/ROADMAP.md`](docs/ROADMAP.md).

## Architecture

Ingestion writes immutable raw artifacts to object storage (local filesystem
today, S3-compatible later), normalizes into PostgreSQL, and serves `/v1`
from the database only.

See:

- [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) — product specification
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md)
- [`docs/LICENSING.md`](docs/LICENSING.md) and [`DATA_LICENSES.md`](DATA_LICENSES.md)

## Quickstart

Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```bash
uv sync
cp .env.example .env
uv run marketdata --help
uv run uvicorn marketdata.api.main:app --reload
```

Health check (once the API is running):

```bash
curl http://127.0.0.1:8000/v1/health
```

After PostgreSQL is configured and quotes are ingested:

```bash
uv run marketdata coverage --date 2026-08-21
curl "http://127.0.0.1:8000/v1/coverage?date=2026-08-21"
```

Coverage scores a CSV universe against stored quotes. It does not fetch
providers. See [`docs/COVERAGE.md`](docs/COVERAGE.md).

PostgreSQL is required for migrations and later ingestion, not for the health
endpoint or unit tests.

```bash
uv run alembic upgrade head
```

## License

Source code: Apache License 2.0. Market data remains under each source's terms.
