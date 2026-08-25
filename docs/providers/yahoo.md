# Yahoo Finance (local / POC)

Unofficial global EOD for local coverage experiments (AAPL, MSFT, SPY,
ASML.AS, …). Not a licensed public equity feed.

`yfinance` is used only inside `providers/yahoo.py`. Domain, ingestion, API, and
CLI must not import it.

## Operational flags

```text
ingestion_enabled: true
public_api_enabled: false
public_dataset_enabled: false
redistribution_policy: UNKNOWN
is_official: false
```

`yfinance` is Apache-2.0; Yahoo data is not licensed for redistribution. Public
`/v1/quotes` omits this source via the existing API access gate (ADR-0013). Do
not publish Parquet. Do not commit Yahoo bulk extracts.

See [`LICENSING.md`](../LICENSING.md), [`DATA_LICENSES.md`](../../DATA_LICENSES.md),
and [`adr/0013-yahoo-gating.md`](../adr/0013-yahoo-gating.md).

## Price semantics

History `Close` → `CLOSE`. Do not use `Adj Close` for daily valuation.
`auto_adjust=False` on the history call. `is_official` is always false.

## Identity

Instrument primary key is a UUID. External keys:

- `SOURCE_ID` — Yahoo symbol (for example `AAPL`, `ASML.AS`)
- `YAHOO_SYMBOL` — same value
- `TICKER` — lookup alias only; not the primary key

## Commands

```bash
uv run marketdata ingest yahoo --date 2026-08-21
uv run marketdata ingest yahoo --date 2026-08-21 --symbol AAPL --symbol MSFT
```

`--date` is required. `--symbol` is repeatable and defaults to `AAPL`.

Empty history (weekend or holiday) skips that symbol and does not fabricate a
close.

## API

Public routes must not return Yahoo:

```text
GET /v1/quotes/AAPL          → 404
GET /v1/quotes/AAPL?source=yahoo → 404
```

Inspect locally with the database or `marketdata explain AAPL --date YYYY-MM-DD`.
There is no `/v1/yahoo` route.

Local `marketdata coverage` may count Yahoo `CLOSE` as priced. `GET /v1/coverage`
keeps Yahoo-only names in the universe but marks them
`REDISTRIBUTION_RESTRICTED` with `price=null`. See [`COVERAGE.md`](../COVERAGE.md).
