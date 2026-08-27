# Coverage universe files

`instruments.example.csv` is an **incomplete, growing seed** used by
`marketdata coverage` and `GET /v1/coverage`. It is not a live index product
and will go stale until someone updates it by hand.

Copy it to `instruments.csv` (gitignored) for a local operator universe, or
pass `--universe PATH`.

The same files can opt-in filter B3 BVBG.186 LAST ingest:
`INGEST_UNIVERSE=scratch` (operator file if present, else this example) or
`B3_EQUITY_UNIVERSE_PATH`. Only B3 `equity` rows are used. Default ingest is
still the full 186 file. See [`docs/INGEST_SCHEDULE.md`](../docs/INGEST_SCHEDULE.md).

## Snapshot

- Date recorded in the CSV header (`snapshot_date`).
- **IBOV / SMLL:** one-time B3 theoretical portfolio (“carteira do dia”),
  citing B3 theoretical-portfolio methodology. Not a daily membership sync.
- **S&P 500 / Nasdaq-100 / DJIA:** public composition-page ticker snapshot
  for coverage experiments. This is **not** redistribution of the official
  index products. Do not commit Yahoo bulk extracts.
- **Futures:** hand-authored listed tickers (WIN/IND/WDO/DOL plus several
  DI1 maturities). Front-month codes go stale; update by hand.

Russell 2000, funds, Tesouro, crédito, Nasdaq Composite, and every DI expiry
are out of this seed.

## Columns

See [`docs/COVERAGE.md`](../docs/COVERAGE.md).
