# CFTC Commitments of Traders

Weekly futures snapshot for a **short allowlist** only. Persist
`cot_snapshots` (`source=cftc`). Do not dump the CFTC universe into Postgres.

## Allowlist

`config/cot_contracts.csv` matches `contract_market_name` by case-insensitive
substring:

| code | kind |
|---|---|
| SPX | equity index (E-mini S&P 500) |
| NDX | equity index (Nasdaq-100) |
| DX | USD index |
| US10Y / US2Y | rates |
| CL | WTI |
| HG | copper |
| GC | gold |
| BRL | Brazilian real (if present) |

One row per contract per report date. Latest snapshot only is fetched
(`$limit=400`, newest first).

## Download

```text
https://publicreporting.cftc.gov/resource/72hh-3qpy.json
https://publicreporting.cftc.gov/resource/gpe5-46if.json
```

Disaggregated futures-only (commodities) plus Traders in Financial Futures.
Live HTTP failure **skips success**. Tests use fixtures; CI does not call CFTC.

## Commands

```bash
uv run marketdata ingest cftc --date 2026-08-21
```

Honor `CFTC_PROVIDER_ENABLED`. There is no `/v1/cot` route in this milestone;
rows stay in `cot_snapshots` for later ATLAS use.
