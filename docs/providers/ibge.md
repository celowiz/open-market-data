# IBGE SIDRA

Small official Brazil macro set. Persist as `market_series` observations,
`source=ibge`.

## Series

| Code | SIDRA | Variable | Notes |
|---|---|---|---|
| `IBGE:IPCA_MOM` | table 1737 | v/63 | IPCA monthly variation, percent |
| `IBGE:IPCA_12M` | table 1737 | v/2265 | IPCA 12-month accumulated, percent |

PIB (table 1620) is **not ingested**. It stays a documented stub so Neon Free
does not grow a second national-accounts history.

## Download

```text
https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/63/p/{YYYYMM}?formato=json
https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2265/p/{YYYYMM}?formato=json
```

`--date` selects the calendar month (`YYYYMM`). Empty / `...` SIDRA cells are
skipped. HTTP failures skip that series and do not fail the run.

## Commands

```bash
uv run marketdata ingest ibge --date 2026-08-21
```

Honor `IBGE_PROVIDER_ENABLED`.

## API

```text
GET /v1/series/IBGE:IPCA_MOM
GET /v1/macro
```
