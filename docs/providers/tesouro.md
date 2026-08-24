# Tesouro Direto

Ingests the Tesouro Transparente CKAN CSV (not the Data Lake REST API, which
returned 404 during planning). PYield is not used as a price source.

```bash
uv run marketdata ingest tesouro --date 2026-08-21
```

Identity is `title_type:maturity_date`, for example `LTN:2029-01-01`.
`PU Base Manha` maps to `PU_BASE`.

```text
GET /v1/quotes/LTN:2029-01-01?price_type=PU_BASE
```
