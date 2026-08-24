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

Foundation is in progress. Seed architecture documentation is in `docs/`.
The public API and bulk datasets are not generally available yet. Local
CVM, Tesouro, and BCB ingestion plus `/v1` query routes exist for development.

The first functional vertical after Foundation is **CVM fund NAV**.

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

PostgreSQL is required for migrations and later ingestion, not for the health
endpoint or unit tests.

```bash
uv run alembic upgrade head
```

## License

Source code: Apache License 2.0. Market data remains under each source's terms.
