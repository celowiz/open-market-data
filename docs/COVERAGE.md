# Coverage engine

Coverage answers: what percentage of a **caller-supplied CSV universe** can be
priced on a given date from quotes **already stored in PostgreSQL**?

It does not invent the universe and does not call providers at request time.
Ingestion stays a separate command (`marketdata ingest …`).

## Commands

```bash
uv run marketdata coverage --date 2026-08-21
uv run marketdata coverage --date 2026-08-21 --universe config/instruments.csv
uv run marketdata coverage --date 2026-08-21 --public
```

Default universe path: `config/instruments.csv` if present, else
[`config/instruments.example.csv`](../config/instruments.example.csv).

```text
GET /v1/coverage?date=YYYY-MM-DD&universe=example|operator|scratch
GET /v1/coverage/span?universe=example|operator|scratch
```

`universe` is a name, never a filesystem path. `example` is the committed
coverage seed (includes US ticker experiments). `scratch` is the committed
IBOV/SMLL/futures list used by `INGEST_UNIVERSE=scratch`. `operator` is
gitignored `config/instruments.csv` (404 if missing). There is no `/v1/yahoo`
route.

`GET /v1/coverage/span` is a cheap `min`/`max`/`count` aggregate of quotes
already stored for that universe. It does **not** run the date-by-date
coverage engine (which is too slow to use as a backfill progress bar).
Optional `source=b3` filters the aggregate. The Explorer coverage page
loads span for the summary and only calls `/v1/coverage?date=` on demand.

The API always uses **public** mode. The CLI defaults to **local** mode.
`--public` applies the same gate as the API (`public_api_enabled`).

## Local vs public

Public coverage reuses [`src/marketdata/api/access.py`](../src/marketdata/api/access.py).
A source with `public_api_enabled=false` stays in the universe but is
`RESTRICTED` with `missing_reason=REDISTRIBUTION_RESTRICTED` and `price=null`.
Yahoo and B3 names may be `PRICED` under current operational flags. Coverage
does not write Parquet. ODbL bulk files are a separate command; see
[`DATASETS.md`](DATASETS.md).

## Expected observations

- B3 equity → `LAST`
- B3 future → `OFFICIAL_SETTLEMENT` (never last trade as settlement)
- Yahoo equity → `CLOSE`

Never fabricate a price. Never carry yesterday’s last forward as today.
`NO_TRADE` is the coverage spelling of `NO_PUBLIC_PRICE` in
[`PRICE_SEMANTICS.md`](PRICE_SEMANTICS.md).

## CSV

Columns follow the project brief: `instrument_id` (optional UUID), `asset_class`,
`ticker`, `isin`, `cnpj_fundo_classe`, `title_type`, `maturity_date`, `exchange`,
`currency`, `preferred_provider`, plus optional `universe` tag.

Futures are one listed ticker per row (`DI1F27`, not a generic `DI`).

The committed example is an **incomplete snapshot**. See
[`config/README.md`](../config/README.md). Do not scrape live index constituents
at coverage time. US rows are a ticker experiment, not licensed index-constituent
redistribution.

## Read path (API)

`GET /v1/coverage` still scores the **whole** named CSV, then slices
`results[cursor:cursor+limit]`. Totals (`priced`, `missing_reason_counts`) are
universe-wide. The contract is unchanged.

The slow path was not a missing index and not a Python date walk. For each
CSV row the store issued separate SQL for source, identifier resolve, the
session quote, `NO_PUBLIC_PRICE` events, ingest success, and `MAX(reference_date)`
when the session was missing. Scratch is ~165 names. On Neon Free
(`instrument_quotes` ~139 MB / ~350k rows, history back to 2004) that is
hundreds of Railway→Neon round trips. A 2024-06-03 scratch request took ~199s
with 146 `STALE` results.

`SessionCoverageStore.prefetch_universe` now loads that snapshot in a handful
of SELECTs, then `_evaluate_row` answers from memory:

1. `sources` for preferred providers in the CSV.
2. `instrument_identifiers` for all tickers/ISINs in the CSV
   (`ix_instrument_identifiers_type_value`).
3. `instrument_quotes` for those instrument ids on the requested date
   (`uq_instrument_quotes_identity` / `(instrument_id, reference_date)`).
   Highest `revision` wins in Python.
4. `MAX(reference_date)` grouped by `(instrument_id, price_type, source)` for
   `reference_date < :date` — Nested Loop + index-only scan on
   `uq_instrument_quotes_identity`, not a seq scan. EXPLAIN ANALYZE for three
   IBOV names was <1ms.
5. Successful `ingestion_runs` for those providers and date.
6. `quality_events` with `event_type = NO_PUBLIC_PRICE` for those ids.

No migration. Existing `(instrument_id, reference_date)` indexes are enough.
Prefetch is read-only (`SELECT`); it does not lock `instrument_quotes` and is
safe while backfill inserts.

Neighboring Explorer reads:

- `GET /v1/instruments` used `SELECT DISTINCT instrument_id FROM instrument_quotes`
  (seq scan, ~167ms on Neon plus transfer). It now uses `LATERAL … LIMIT 1`
  correlated to `instruments` so PostgreSQL nested-loops the unique quote
  index (~59ms for 21 rows, scales with instrument count).
- Quote history hydrates `source` and `raw_artifact_sha256` in two IN queries
  per page instead of `session.get` per row.

## Out of scope

Live rebalancing, licensed US index feeds, ANBIMA, fair-value fills, funds,
Tesouro, crédito, Russell 2000, Nasdaq Composite, every DI expiry.
