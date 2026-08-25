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
migrations or database tests. Object storage defaults to `./data` on the
filesystem. Neon, Railway, and Cloudflare are not required.

Daily ingest: `uv run marketdata ingest <provider> --date YYYY-MM-DD`.
Multi-year backfill is **Phase 12** (not implemented yet). Do not commit
files under `data/`.

Optional local PostgreSQL:

```bash
docker compose up -d postgres
```

Apply migrations:

```bash
uv run alembic upgrade head
```

## Quality checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Format:

```bash
uv run ruff format .
```

Unit tests must not call live market-data websites. Tests that need PostgreSQL
are marked `db`. Tests that hit real sources are marked `integration` and are
not required on every commit.

## Adding a provider

Provider work starts in Phase 2 (CVM). Follow
`docs/IMPLEMENTATION_PLAN.md` and later `docs/contributing/adding-a-provider.md`.

Do not import third-party source clients outside `src/marketdata/providers/`.

## Pull requests

- Keep the change scoped to one phase or one concern.
- Do not commit `.env`, credentials, or files under `data/`.
- Do not add cloud resources or secrets.
