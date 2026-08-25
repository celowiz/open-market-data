# Banco Central do Brasil

SGS series are stored as market series observations, not instrument quotes.

`python-bcb` is used only inside `providers/bcb.py`.

## Series codes

Daily ingest and range backfill cover these five SGS series:

| Series code | SGS id | Name | Unit |
|---|---|---|---|
| `BCB:SELIC_DAILY` | 11 | Selic over | `percent_per_day` |
| `BCB:CDI_DAILY` | 12 | CDI | `percent_per_day` |
| `BCB:SELIC_TARGET` | 432 | Selic target | `percent_per_year` |
| `BCB:PTAX_USD_SELL` | 1 | PTAX USD sell | `BRL_per_USD` |
| `BCB:PTAX_USD_BUY` | 10813 | PTAX USD buy | `BRL_per_USD` |

History queries use `chunk_date_range(..., years=10)`: each SGS call spans **at most 10 years**. A 26-year window is three (or so) chunked requests **per series**, not one HTTP call per calendar day.

## Ingest (one calendar day)

```bash
uv run marketdata ingest bcb --date 2026-08-21
```

## Backfill (multi-year)

```bash
uv run marketdata backfill bcb --start 2000-01-01 --end 2026-08-24
```

`--start` and `--end` are inclusive. Resume is on by default: completed date windows whose `chunk_end` is at or before `state/backfill/bcb.json` `last_completed` are skipped. Raw JSON is stored per series and chunk at `raw/bcb/backfill/{code}/{chunk_start}_{chunk_end}.json`, with `:` in the series code replaced by `_` so local filesystem storage works on Windows (for example `BCB_CDI_DAILY`).

```text
GET /v1/series/BCB:CDI_DAILY/observations
GET /v1/series/12/observations
```

`marketdata publish datasets` includes BCB SGS / PTAX observations in the
`rates` Parquet catalog. See [`DATASETS.md`](../DATASETS.md).
