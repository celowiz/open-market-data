# CVM Informe Diário (fund NAV)

## Source

- Dataset: https://dados.cvm.gov.br/dataset/fi-doc-inf_diario
- Monthly ZIP (rolling 12 months): `https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{YYYY}{MM}.zip`
- Yearly HIST ZIP (older months): `https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/HIST/inf_diario_fi_{YYYY}.zip`
- Cadastro ZIP (RCVM 175): `https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip`
- License: ODbL 1.0 (`PUBLIC_WITH_ATTRIBUTION`)

Bare Informe `.csv` URLs return HTTP 403. This provider always downloads ZIP
files. Cadastro uses the same ZIP pattern (`registro_fundo_classe.zip`).

Do **not** fetch `DADOS/inf_diario_fi_{YYYY}{MM}.zip` for archive years that
CVM has moved under `DADOS/HIST/` (for example 2018). HIST years are one ZIP
per calendar year; inner members are monthly CSVs such as
`inf_diario_fi_YYYYMM.csv`.

## Cadastro (reference data, not a quote stream)

Daily ingest and backfill fetch `registro_fundo_classe.zip` once per run and
store it at `raw/cvm/cadastro/registro_fundo_classe.zip`. Inner member
`registro_classe.csv` is joined to Informe rows on digits-only
`CNPJ_FUNDO_CLASSE` = `CNPJ_Classe`.

The persist filter uses `Classificacao`. Those strings are the same vocabulary
as `cad_fi.csv` `CLASSE` for FIF funds. Verified labels from the live files:

| `Classificacao` / cad_fi `CLASSE` | Where it appears |
|---|---|
| `Multimercado` | FIF |
| `Ações` | FIF |
| `Renda Fixa` | FIF |
| `Cambial`, `FMP-FGTS` | FIF (rare) |
| *(blank)* | FII, FIDC, FIP, FIAGRO, and other `Tipo_Classe` values |

`Tipo_Classe` is stored on the instrument as metadata (`tipo_classe`) but is
not the allowlist key. There is no distinct ETF/`índice` `CLASSE` label.

`cad_fi.csv` is the non-adapted RCVM 175 snapshot (`CNPJ_FUNDO`). Almost every
row is `CANCELADA`. Era C Informe identity is class-level `CNPJ_FUNDO_CLASSE`,
so ingest joins `registro_classe.csv`, not `cad_fi.csv`.

Class is written onto the **instrument** (`metadata.classe`, display name from
`Denominacao_Social`). `instrument_type` stays `fund_class`. FUND_NAV quote
rows are unchanged (`vl_patrim_liq`, `schema_era`, `subclass_id` only).

## Class filter (`CVM_CLASSES`)

Comma-separated allowlist of exact `CLASSE` / `Classificacao` labels.

- Empty / unset: persist every Informe row (backward compatible).
- Set: persist only joined classes in the list. Rows with no cadastro match,
  blank `Classificacao` (FII/FIDC/…), or a label outside the list are skipped.

Scratch / Neon Free default in `.env.example`:

```text
CVM_CLASSES=Multimercado,Ações
```

That keeps FIF Multimercado and Ações and skips FII, FIDC, Renda Fixa, and
unclassified CNPJs. Operators can add `Renda Fixa` later; do not invent labels.

GitHub Actions `ingest-cvm.yml` stays **workflow_dispatch only**. The job sets
`CVM_CLASSES` to `Multimercado,Ações` unless repository variable `CVM_CLASSES`
overrides it. `DATABASE_URL` remains an Actions **secret** (no value in git).

## Identity

`(CNPJ_FUNDO_CLASSE, ID_SUBCLASSE, DT_COMPTC)` with `CNPJ_FUNDO` as a legacy alias.
Empty subclass is stored as null. CNPJ matching ignores punctuation.

## Price semantics

`VL_QUOTA` → `FUND_NAV`. `VL_PATRIM_LIQ` is metadata, not a unit price.

Schema eras A/B/C are detected from the CSV header. See `docs/DATA_SOURCES.md`.

## Commands

Daily ingest (rolling monthly `DADOS/` window; `--lookback-days` defaults to
`RECENT_REPROCESS_DAYS` / 90). Use `0` to fetch only the month of `--date`.
Cadastro is fetched every run. The class filter applies to daily ingest and
backfill.

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

Start with one recent year. Full HIST is tens of millions of quotes; the class
filter still has to parse each monthly CSV.

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
