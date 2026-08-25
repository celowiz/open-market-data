# CVM Informe Diário (fund NAV)

## Source

- Dataset: https://dados.cvm.gov.br/dataset/fi-doc-inf_diario
- Monthly ZIP: `https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{YYYY}{MM}.zip`
- License: ODbL 1.0 (`PUBLIC_WITH_ATTRIBUTION`)

Bare `.csv` URLs return HTTP 403. This provider always downloads ZIP files.

## Identity

`(CNPJ_FUNDO_CLASSE, ID_SUBCLASSE, DT_COMPTC)` with `CNPJ_FUNDO` as a legacy alias.
Empty subclass is stored as null. CNPJ matching ignores punctuation.

## Price semantics

`VL_QUOTA` → `FUND_NAV`. `VL_PATRIM_LIQ` is metadata, not a unit price.

Schema eras A/B/C are detected from the CSV header. See `docs/DATA_SOURCES.md`.

## Commands

```bash
uv run marketdata ingest cvm --date 2026-08-21
uv run marketdata ingest cvm --date 2026-08-21 --lookback-days 0
uv run marketdata explain 00017024000153 --date 2026-08-03
```

`--lookback-days` defaults to `RECENT_REPROCESS_DAYS` (90). Use `0` to fetch
only the month of `--date`.

Yearly archive files under `DADOS/HIST/` and a `backfill cvm --start --end`
command are **Phase 12**. Do not loop `ingest cvm` across decades without that
CLI (memory, duplicate monthly fetches, missing HIST URLs).

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
