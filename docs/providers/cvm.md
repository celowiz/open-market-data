# CVM Informe Diário (fund NAV)

## Source

- Dataset: https://dados.cvm.gov.br/dataset/fi-doc-inf_diario
- Monthly ZIP (rolling 12 months): `https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{YYYY}{MM}.zip`
- Yearly HIST ZIP (older months): `https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/HIST/inf_diario_fi_{YYYY}.zip`
- License: ODbL 1.0 (`PUBLIC_WITH_ATTRIBUTION`)

Bare `.csv` URLs return HTTP 403. This provider always downloads ZIP files.

Do **not** fetch `DADOS/inf_diario_fi_{YYYY}{MM}.zip` for archive years that
CVM has moved under `DADOS/HIST/` (for example 2018). HIST years are one ZIP
per calendar year; inner members are monthly CSVs such as
`inf_diario_fi_YYYYMM.csv`.

## Identity

`(CNPJ_FUNDO_CLASSE, ID_SUBCLASSE, DT_COMPTC)` with `CNPJ_FUNDO` as a legacy alias.
Empty subclass is stored as null. CNPJ matching ignores punctuation.

## Price semantics

`VL_QUOTA` → `FUND_NAV`. `VL_PATRIM_LIQ` is metadata, not a unit price.

Schema eras A/B/C are detected from the CSV header. See `docs/DATA_SOURCES.md`.

## Commands

Daily ingest (rolling monthly `DADOS/` window; `--lookback-days` defaults to
`RECENT_REPROCESS_DAYS` / 90). Use `0` to fetch only the month of `--date`.

```bash
uv run marketdata ingest cvm --date 2026-08-21
uv run marketdata ingest cvm --date 2026-08-21 --lookback-days 0
uv run marketdata explain 00017024000153 --date 2026-08-03
```

Historical backfill (`--lookback-days` does **not** apply). Months inside the
live 12-month `DADOS/` window use monthly ZIPs; older months use that year's
HIST ZIP **once**, stored at `raw/cvm/hist/inf_diario_fi_{YYYY}.zip`. Progress
is checkpointed after each month (`last_completed=YYYY-MM`). Optional
`--max-months` is a safety cap (default unlimited).

```bash
uv run marketdata backfill cvm --start 2025-01-01 --end 2026-08-24
uv run marketdata backfill cvm --start 2018-01-01 --end 2026-08-24 --max-months 3
```

Start with one recent year. Full HIST is tens of millions of quotes.

Months that have aged out of the 12-month `DADOS/` window but are not yet
published as a complete `HIST/inf_diario_fi_{YYYY}.zip` may 404 until CVM
promotes that year. Narrow `--start/--end` or wait; this adapter will not
guess monthly URLs for archive years.

## API

```text
GET /v1/funds/{cnpj}/quotes
GET /v1/funds/{cnpj}/quotes/latest
GET /v1/sources
```

The `{identifier}` path should use digits-only CNPJ (punctuation in the URL
path is parsed as extra segments). Query matching still strips punctuation.

`marketdata publish datasets` includes CVM fund NAVs (`FUND_NAV`) in the
`quotes` and `fund_nav` Parquet catalogs when
`PUBLIC_DATASET_PUBLICATION_ENABLED=true`. See [`DATASETS.md`](../DATASETS.md).
