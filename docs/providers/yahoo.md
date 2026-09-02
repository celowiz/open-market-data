# Yahoo Finance (local / POC)

Unofficial global EOD for local coverage experiments and the scratch B3 equity
universe (`PETR4.SA`, …). Not a licensed public equity feed.

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

History `Close` → `CLOSE` (session close; daily valuation). History `Adj Close`
→ `ADJUSTED_CLOSE` using Yahoo's column as published — do not rebuild adjusted
close from dividends. `auto_adjust=False` on the history call. `is_official` is
always false.

Default symbols are scratch-universe B3 equities mapped as `{TICKER}.SA`
(`config/instruments.scratch.csv`). Futures (`WIN*` / `IND*` / `WDO*` / `DOL*` /
`DI1*`) are skipped. There is no AAPL default.

## Identity

Instrument primary key is a UUID. External keys:

- `SOURCE_ID` — Yahoo symbol (for example `PETR4.SA`, `AAPL`)
- `YAHOO_SYMBOL` — same value
- `TICKER` — lookup alias only; not the primary key. Scratch B3 names use the
  `.SA` suffix so they do not collide with official B3 `PETR4`.

## Commands

```bash
uv run marketdata ingest yahoo --date 2026-08-21
uv run marketdata ingest yahoo --date 2026-08-21 --symbol PETR4.SA --symbol VALE3.SA
```

`--date` is required. `--symbol` is repeatable; when omitted, ingest uses the
scratch equity universe (`{TICKER}.SA`) plus `config/yahoo_macro.csv`
(CL=F, GC=F, HG=F, DX-Y.NYB, BRL=X). Do not default to AAPL.
`B3_EQUITY_UNIVERSE_PATH` wins when set; `INGEST_UNIVERSE=scratch` uses the same
CSV as B3 scratch ingest; an empty `INGEST_UNIVERSE` still reads
`config/instruments.scratch.csv`. GitHub Actions `ingest-yahoo.yml` runs nightly
at 00:00 America/Sao_Paulo and defaults `--date` to yesterday BRT, walking
backward across Saturday/Sunday so Monday 00:00 ingests Friday.

Empty history for one symbol (weekend, holiday, or a missing Yahoo name) skips
that symbol and does not fail the job or fabricate a close. If mapped equities
are greater than zero and nothing is fetched/persisted on a weekday, the job
fails. The same empty persist on Saturday/Sunday logs a warning and succeeds.

## Historical backfill (local / POC)

Range backfill is **one `fetch_history` call per symbol**, not one HTTP call per
calendar day. `public_api_enabled` is true so quotes appear on `/v1`. Yahoo must
not be published as Parquet.

```bash
uv run marketdata backfill yahoo --start 2020-01-01 --end 2026-08-24
uv run marketdata backfill yahoo --start 2020-01-01 --end 2026-08-24 --symbol AAPL
```

Behavior:

- Default symbols match daily ingest (scratch `{TICKER}.SA` equities unless
  `--symbol` is passed).
- The `[start, end]` window is inclusive. Ingestion calls
  `YahooProvider.fetch_history(symbol, start=start, end=end + 1 day)` so the
  last session is included the same way as daily ingest (yfinance `end` is
  exclusive).
- Persists `Close` as `CLOSE` and Yahoo `Adj Close` as `ADJUSTED_CLOSE`. Never
  recomputes adj from dividends.
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

`GET /v1/coverage/span` lists official B3 names from the CSV and, for B3
equities, a companion Yahoo row as `{TICKER}.SA` so `PETR4.SA` is visible
without colliding with official `PETR4`. `source=b3` hides the companions.
`source=yahoo` shows `PETR4.SA` instead of `PETR4`.

Local `marketdata coverage` and `GET /v1/coverage` may count Yahoo `CLOSE` as
priced while `public_api_enabled` is true. See [`COVERAGE.md`](../COVERAGE.md).
