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
GET /v1/coverage?date=YYYY-MM-DD&universe=example|operator
```

`universe` is a name, never a filesystem path. `example` is the committed seed.
`operator` is gitignored `config/instruments.csv` (404 if missing). There is no
`/v1/yahoo` route.

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

## Out of scope

Live rebalancing, licensed US index feeds, ANBIMA, fair-value fills, funds,
Tesouro, crédito, Russell 2000, Nasdaq Composite, every DI expiry.
