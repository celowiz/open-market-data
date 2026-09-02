# FRED (Federal Reserve Economic Data)

Allowlisted US/global macro series via the public FRED Observations API.
Persisted as instrument quotes (`price_type=REFERENCE`, `source=fred`).

A FRED API key is required (`FRED_API_KEY`). When the key is unset, the CLI
and `ingest-fred.yml` **succeed with skip** (same pattern as publish-datasets
without R2). Do not call the API without a key.

## Series allowlist

Only `config/fred_series.csv`. Do not ingest the FRED catalog.

| series_id | Notes |
|---|---|
| `DGS2` | 2-year Treasury constant maturity |
| `DGS10` | 10-year Treasury constant maturity |
| `T10Y2Y` | 10y−2y spread |
| `DTWEXBGS` | Trade Weighted U.S. Dollar Index: Broad, Goods (not ICE DXY) |
| `VIXCLS` | CBOE VIX |
| `PAYEMS` | All Employees, Total Nonfarm |
| `DCOILWTICO` | WTI Cushing, OK |
| `PCOPPUSDM` | Global copper price |
| `IQ12260` | ICE Gold Price 10:30 London. `GOLDAMGBD228NLBM` is discontinued |

Yahoo `CL=F` / `GC=F` / `DX-Y.NYB` are distinct unofficial identifiers
(ADR-0013). Do not treat them as the same series as FRED.

## Download

```text
https://api.stlouisfed.org/fred/series/observations
  ?series_id={id}&api_key={key}&file_type=json
  &observation_start=YYYY-MM-DD&observation_end=YYYY-MM-DD
```

Observations with value `.` are skipped (FRED missing-value marker). Never
fabricate a carry-forward.

## Commands

```bash
uv run marketdata ingest fred --date 2026-08-21
```

Daily ingest looks back a few calendar days so weekends/holidays still land
the latest published observation. Honor `FRED_PROVIDER_ENABLED`.

## API

```text
GET /v1/quotes/DGS10?source=fred
GET /v1/macro
```

Instrument identifiers are the FRED series id (`TICKER` and `SOURCE_ID`).
The canonical code in config is `FRED:DGS10`.
