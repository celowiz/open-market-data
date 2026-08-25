# Tesouro Direto

Ingests the Tesouro Transparente CKAN CSV (not the Data Lake REST API, which
returned 404 during planning). PYield is not used as a price source.

```bash
uv run marketdata ingest tesouro --date 2026-08-21
```

That command filters the official CSV to one `Data Base`. Full history since
2002 is **Phase 12**: `marketdata backfill tesouro --start 2002-01-01 --end
YYYY-MM-DD` (one download, persist every day in range).

Identity is `title_type:maturity_date`, for example `LTN:2029-01-01`.
`PU Base Manha` maps to `PU_BASE`.

```text
GET /v1/quotes/LTN:2029-01-01?price_type=PU_BASE
```
