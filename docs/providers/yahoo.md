# Yahoo Finance (local / POC)

Unofficial global EOD for local coverage experiments (AAPL, MSFT, SPY,
ASML.AS, …). Not a licensed public equity feed.

`yfinance` is used only inside `providers/yahoo.py`. Domain, ingestion, API, and
CLI must not import it.

## Operational flags

```text
ingestion_enabled: true
public_api_enabled: true
public_dataset_enabled: false
redistribution_policy: UNKNOWN
is_official: false
```

`yfinance` is Apache-2.0; Yahoo data is not licensed for redistribution. The
public API currently serves this source when `public_api_enabled` is true
(temporary, for local testing). Do not publish Parquet. Do not commit Yahoo
bulk extracts.

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

## Historical backfill (local / POC)

Range backfill is **one `fetch_history` call per symbol**, not one HTTP call per
calendar day. `public_api_enabled` is true so quotes appear on `/v1`. Yahoo must
not be published as Parquet.

```bash
uv run marketdata backfill yahoo --start 2020-01-01 --end 2026-08-24
uv run marketdata backfill yahoo --start 2020-01-01 --end 2026-08-24 --symbol AAPL
```

Behavior:

- Default symbols match daily ingest (`AAPL` unless `--symbol` is passed).
- The `[start, end]` window is inclusive. Ingestion calls
  `YahooProvider.fetch_history(symbol, start=start, end=end + 1 day)` so the
  last session is included the same way as daily ingest (yfinance `end` is
  exclusive).
- Persists `Close` as `CLOSE`. Never `Adj Close`.
- Raw JSON: `raw/yahoo/backfill/{symbol}/{start}_{end}.json` with `close` stored
  as a decimal string (not a binary float).
- Object-storage checkpoint: `state/backfill/yahoo.json` (`provider="yahoo"`),
  updated after each symbol and marked `succeeded` at the end. Postgres
  `COMMIT`s after each symbol. The runner `./data` checkpoint does not survive
  between GitHub Actions jobs.
- Database upserts flush every 1000 quotes.

Tests inject `history_rows` to stay offline (no Yahoo HTTP).

## API

Public routes return Yahoo when the source flag is on:

```text
GET /v1/quotes/AAPL          → 200 (CLOSE)
GET /v1/quotes/AAPL?source=yahoo → 200
```

There is no `/v1/yahoo` route.

Local `marketdata coverage` and `GET /v1/coverage` may count Yahoo `CLOSE` as
priced while `public_api_enabled` is true. See [`COVERAGE.md`](../COVERAGE.md).
