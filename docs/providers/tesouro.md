# Tesouro Direto

Ingests the Tesouro Transparente CKAN CSV (not the Data Lake REST API, which
returned 404 during planning). PYield is not used as a price source.

```bash
uv run marketdata ingest tesouro --date 2026-08-21
```

Daily ingest filters the official CSV to one `Data Base`. Historical range
ingest downloads that CSV **once** and persists every `Data Base` in
`--start`/`--end` (inclusive):

```bash
uv run marketdata backfill tesouro --start 2002-01-01 --end 2026-08-24
```

Identity is `title_type:maturity_date`, for example `LTN:2029-01-01`.
`PU Base Manha` maps to `PU_BASE`.

```text
GET /v1/quotes/LTN:2029-01-01?price_type=PU_BASE
```

`marketdata publish datasets` includes Tesouro quotes (`PU_BASE` and the other
stored Tesouro `price_type`s) in the `quotes` Parquet catalog. See
[`DATASETS.md`](../DATASETS.md).
