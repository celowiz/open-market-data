# AGENTS.md

## Project

This repository contains an open-source financial market data platform.

The goal is to collect financial market data from public and preferably official
sources, preserve provenance, normalize heterogeneous datasets, expose a public
API, and publish reusable public datasets when licensing allows redistribution.

Before making architectural changes, read:

- `docs/PROJECT_BRIEF.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/DATA_SOURCES.md`
- `docs/PRICE_SEMANTICS.md`
- `docs/LICENSING.md`

`docs/PROJECT_BRIEF.md` is the main product specification.

---

## Core principles

- Python 3.12+
- Use `uv` for Python dependency management.
- Prefer Polars over pandas for our own data processing.
- PostgreSQL is the serving database.
- FastAPI is the public API.
- Cloudflare R2 is the preferred production object storage.
- The official PostgreSQL deployment is expected to use Neon.
- The official FastAPI deployment is expected to use Railway.
- GitHub Actions will initially orchestrate scheduled ingestion.
- Public bulk datasets should preferably use Parquet.
- External data sources must be isolated behind provider/adapters.
- Preserve original raw artifacts whenever possible.
- Preserve full data provenance.
- Never use `float` for persisted financial prices.
- Never silently convert between different financial price semantics.
- Never redistribute data unless the source licensing policy explicitly allows it.
- Never commit secrets.

---

## Development philosophy

Prefer simple and explicit architecture.

Avoid premature use of:

- microservices
- Kubernetes
- Kafka
- Celery
- Redis
- Airflow
- complex plugin frameworks

unless a concrete requirement justifies them.

The project must remain self-hostable.

Local development must not depend on Neon, Railway or Cloudflare.

Prefer:

- local PostgreSQL
- local filesystem object storage

for development.

Cloud services are deployment choices, not domain dependencies.

---

## Domain rules

Do not treat every financial datapoint as a generic quote.

The domain should distinguish at least:

- instrument quotes
- market series observations
- curve points

Examples:

- PETR4 close → instrument quote
- DI future settlement → instrument quote with `OFFICIAL_SETTLEMENT`
- fund unit value → instrument quote / fund unit value
- CDI → market series observation
- PTAX → market series observation
- IPCA → market series observation
- DI curve point → curve point

Instrument identifiers must be stable.

Do not use ticker as the universal primary key.

Support identifiers such as:

- ticker
- ISIN
- CNPJ / CNPJ_FUNDO_CLASSE
- exchange-specific identifier
- source-specific identifier
- title type + maturity date when appropriate

---

## Data provenance

Every normalized observation should make it possible to determine:

- source
- reference date
- retrieval timestamp
- price/value semantics
- original raw artifact
- ingestion run
- revision when applicable

Never fabricate missing values.

Do not silently use stale values as current values.

---

## Data licensing

Code licensing and data licensing are separate concerns.

A provider may be:

- enabled for ingestion
- disabled for public API
- disabled for public dataset publication

until redistribution rights are confirmed.

When licensing is unclear, default to no public redistribution.

---

## Infrastructure

The intended official deployment currently uses:

- Neon PostgreSQL
- Cloudflare R2
- Railway
- GitHub Actions
- Cloudflare CDN / WAF
- GitHub Pages for documentation
- Next.js + Vercel as the public Data Explorer in **Phase 13** (after
  Phase 12 historical backfill; Explorer consumes FastAPI only)

MCP access for Neon, Cloudflare and Railway may be available in the development
environment.

Prefer official MCP integrations or official CLIs for infrastructure operations.

Never expose credentials in prompts, code, logs or commits.

---

## Workflow

For substantial tasks:

1. Read the relevant project documentation.
2. Inspect the existing code before proposing changes.
3. Create a scoped plan.
4. Use research subagents when independent investigation is useful.
5. Use isolated worktrees only when concurrent agents will modify independent code.
6. Implement one coherent milestone at a time.
7. Run tests, linting and type checking.
8. Review the final diff for unrelated changes.
9. Update documentation when decisions change.
10. Stop before starting the next milestone unless explicitly instructed.

The parent agent owns final integration.

Do not allow multiple agents to concurrently edit the same files in the same checkout.

---

## Quality checks

Expected commands will initially be:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

---

## Object Storage

Cloudflare R2 is the intended production object storage, but R2 is not currently enabled.

Do not require Cloudflare R2 credentials during the initial development phases.

Local development must use the filesystem object-storage adapter.

Design object storage behind a generic interface so that an S3-compatible
implementation can be enabled later without changing domain or ingestion code.

Do not create Cloudflare R2 resources unless explicitly requested.

---

## Current Infrastructure Availability

The following managed services have been selected for the official deployment,
but not all production resources exist yet.

### Neon

- Account configured.
- Neon MCP is authenticated and available.
- Agents may inspect Neon through MCP.
- Do not create production resources during planning.
- Development database resources may be created only when required by the
  approved implementation phase.

### Railway

- Account configured.
- Railway Remote MCP is expected to be available through OAuth.
- No Railway project currently exists.
- Do not create Railway projects or deploy services during discovery or
  foundation unless explicitly required by the current implementation phase.

### Cloudflare

- Account exists.
- Cloudflare R2 is not currently enabled.
- Do not require R2 or Cloudflare credentials during initial development.
- Use the local filesystem object-storage implementation.

The intended production object storage remains S3-compatible, with Cloudflare R2
as the current preferred future provider.

### General Rule

Cloud infrastructure must not block local development.

Agents must not create paid resources, enable billing, add payment methods,
or provision production infrastructure without explicit user approval.