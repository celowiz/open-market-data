# ADR-0001: PostgreSQL as the serving database

- Status: Accepted
- Date: 2026-08-24

## Context

The platform needs a serving database for instruments, quotes, series, and
provenance. Contributors must be able to self-host. Analytics on Parquet can
use DuckDB later, but the public API needs a conventional transactional store.

## Decision

Use **PostgreSQL** as the only serving database for the API.

DuckDB may be used for local Parquet inspection, backfills, and tests. It is
not the serving database.

## Alternatives

- **SQLite:** too weak for concurrent API + ingestion and for NUMERIC-heavy
  workloads at history scale.
- **DuckDB as serving DB:** excellent for analytics files, poor as a network
  service of record for a public API.
- **ClickHouse now:** premature; revisit only after tens of millions of rows
  prove PostgreSQL insufficient.

## Consequences

- SQLAlchemy 2 + Alembic target PostgreSQL dialects only, without Neon-only
  features in domain code.
- Self-hosting requires PostgreSQL (local install or optional Compose).

## Why before Phase 1

Migrations and repositories cannot start without this choice.
