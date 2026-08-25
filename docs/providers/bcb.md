# Banco Central do Brasil

SGS series are stored as market series observations, not instrument quotes.

Initial series: Selic over (11), CDI (12), Selic target (432), PTAX USD sell (1),
PTAX USD buy (10813). History queries are chunked to 10-year windows.

`python-bcb` is used only inside `providers/bcb.py`.

```bash
uv run marketdata ingest bcb --date 2026-08-21
```

Multi-year SGS history (10-year query chunks) is **Phase 12**:
`marketdata backfill bcb --start … --end …`.

```text
GET /v1/series/BCB:CDI_DAILY/observations
GET /v1/series/12/observations
```

`marketdata publish datasets` includes BCB SGS / PTAX observations in the
`rates` Parquet catalog. See [`DATASETS.md`](../DATASETS.md).
