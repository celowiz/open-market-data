# ADR-0007: Parquet for public bulk datasets

- Status: Accepted; implementation in Phase 9
- Date: 2026-08-24

## Context

Large history should not be pulled from the JSON API. Users should be able to
open files with Polars or `read_parquet` in DuckDB.

## Decision

Public bulk datasets use **Parquet** as the primary format, CSV as optional
secondary. Publication is atomic: upload versioned files, validate, then update
the latest manifest.

Only sources with an allowed `redistribution_policy` are published.

## Alternatives

- **CSV-only:** worse types and size.
- **Arrow IPC / DuckDB files:** less universal for download users.
- **JSON lines:** rejected for bulk quotes.

## Consequences

- `pyarrow` (and Polars) become dataset-phase dependencies.
- Manifests include sha256, schema_version, license, row_count.

## Why document now

API pagination design depends on "bulk goes to Parquet".
