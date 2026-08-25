# Architecture Decision Records

ADRs record choices that are expensive to reverse. Trivial implementation
details do not get ADRs.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-postgresql-serving-database.md) | PostgreSQL as serving database | Accepted |
| [0002](0002-neon-managed-postgres.md) | Neon as official managed Postgres | Accepted (deploy later) |
| [0003](0003-object-storage-interface.md) | Object storage interface, filesystem first | Accepted |
| [0004](0004-fastapi-public-api.md) | FastAPI for public API | Accepted |
| [0005](0005-railway-api-hosting.md) | Railway for official API hosting | Accepted (provision after Neon backfill) |
| [0006](0006-github-actions-ingestion.md) | GitHub Actions for ingestion | Accepted (workflows later) |
| [0007](0007-parquet-bulk-datasets.md) | Parquet for bulk datasets | Accepted (Phase 9) |
| [0008](0008-source-code-license.md) | Apache-2.0 for source code | Accepted |
| [0009](0009-mercados-adapter.md) | mercados behind adapters | Accepted with httpx fallback |
| [0010](0010-observation-types.md) | Quotes vs series vs curves | Accepted |
| [0011](0011-instrument-identity.md) | UUID + identifier table | Accepted |
| [0012](0012-first-provider-cvm.md) | CVM as first provider | Accepted |
| [0013](0013-yahoo-gating.md) | Programmatic Yahoo gating | Accepted |
| [0014](0014-b3-redistribution.md) | Default-deny B3 republication | Accepted |
