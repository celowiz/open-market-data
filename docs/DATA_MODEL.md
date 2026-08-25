# Data Model

This document proposes the serving-database schema and domain identities.

Names below are English. Exact SQL types and constraints are created in Phase 1
with SQLAlchemy 2 and Alembic. Do not treat this as an already-applied migration.

Financial prices and rates are persisted as exact decimals (`NUMERIC`), never
`float` / `REAL` / `DOUBLE PRECISION`.

Reference dates are calendar dates, not timestamps. Retrieval and publication
timestamps are timezone-aware UTC.

---

## Core entities

### `sources`

Metadata for each external origin.

| Field | Notes |
|---|---|
| `id` | Stable internal key (UUID or short slug plus UUID) |
| `name` | Machine name: `cvm`, `b3`, `tesouro`, `bcb`, `yahoo`, `anbima` |
| `display_name` | Human label |
| `official` | Boolean |
| `homepage` | Official site |
| `documentation_url` | Dataset or API docs |
| `data_license` | Short license name, e.g. `ODbL-1.0` |
| `redistribution_policy` | Enum, see [`LICENSING.md`](LICENSING.md) |
| `ingestion_enabled` | Capability flag |
| `public_api_enabled` | Capability flag |
| `public_dataset_enabled` | Capability flag |
| `notes` | Free text |

A source can be ingested locally while remaining hidden from public API and
Parquet publication.

### `instruments`

Canonical instrument master. Ticker is never the primary key.

| Field | Notes |
|---|---|
| `id` | UUID primary key |
| `asset_class` | e.g. equity, fund, government_bond, future, fx, rate |
| `instrument_type` | Finer type: listed_share, etf, fii, fund_class, ltn, di1, ... |
| `name` | Display name |
| `currency` | ISO 4217 when the quote is monetary |
| `exchange` / `mic` | Optional venue |
| `issuer` | Optional |
| `maturity_date` | Required for many fixed-income and futures contracts |
| `active_from` / `active_until` | Optional validity |
| `metadata` | JSONB for source-specific extras |

Not every field is required for every instrument.

### `instrument_identifiers`

Multiple external identifiers per instrument, with validity windows.

| Field | Notes |
|---|---|
| `instrument_id` | FK |
| `identifier_type` | See types below |
| `identifier_value` | Normalized string |
| `source_id` | Which source asserted this mapping |
| `valid_from` / `valid_until` | Optional |

Identifier types (initial):

- `TICKER`
- `ISIN`
- `CUSIP`
- `CNPJ`
- `CNPJ_FUNDO_CLASSE`
- `CVM_SUBCLASS_ID`
- `B3_SECURITY_ID`
- `YAHOO_SYMBOL`
- `TITLE_TYPE`
- `SOURCE_ID`

API resolution must accept any of these, including CNPJ with or without punctuation.

### `instrument_quotes`

Normalized observations attached to an instrument.

| Field | Notes |
|---|---|
| `id` | UUID |
| `instrument_id` | FK |
| `reference_date` | Date of the observation |
| `value` | `NUMERIC` — price, PU, NAV, or rate depending on `price_type` |
| `currency` | Present for monetary values |
| `unit` | Optional explicit unit, e.g. `BRL`, `percent_per_day`, `percent_per_year` |
| `price_type` | See [`PRICE_SEMANTICS.md`](PRICE_SEMANTICS.md) |
| `source_id` | FK |
| `source_instrument_id` | Identifier as published by the source |
| `is_official` | Boolean |
| `source_published_at` | Optional |
| `retrieved_at` | UTC timestamp |
| `raw_artifact_id` | FK |
| `ingestion_run_id` | FK |
| `revision` | Integer, starting at 1 |
| `quality_status` | e.g. `ok`, `warning`, `rejected` |
| `metadata` | JSONB |

Idempotency key (conceptual unique constraint):

```text
(instrument_id, reference_date, source_id, price_type, revision)
```

Re-ingesting identical source bytes must not create a new quote row.
If the source republishes different bytes (`sha256` changes), store a new
raw artifact and increment `revision`. Never delete the previous raw artifact.

### `market_series`

Canonical series that are not instruments.

Examples: Selic over (`SGS:11`), CDI (`SGS:12`), PTAX USD sell (`SGS:1`).

| Field | Notes |
|---|---|
| `id` | UUID |
| `code` | Stable public code, e.g. `BCB:SELIC_DAILY` |
| `source_series_id` | e.g. `11` |
| `name` | Display name |
| `source_id` | FK |
| `unit` | Required |
| `value_semantics` | Usually `REFERENCE` |
| `metadata` | JSONB |

### `market_series_observations`

| Field | Notes |
|---|---|
| `series_id` | FK |
| `reference_date` | Date |
| `value` | `NUMERIC` |
| `source_id` | FK |
| `retrieved_at` | UTC |
| `raw_artifact_id` | FK |
| `ingestion_run_id` | FK |
| `revision` | Integer |
| `quality_status` | |
| `metadata` | JSONB |

Idempotency key:

```text
(series_id, reference_date, source_id, revision)
```

Do not model CDI, Selic, or PTAX as tickered instruments.

### `curve_points`

Deferred. Create the table only when a curve provider is implemented.
Until then, do not overload `instrument_quotes` with ETTJ vertices.

### `raw_artifacts`

Every download produces a raw artifact record.

| Field | Notes |
|---|---|
| `id` | UUID |
| `source_id` | FK |
| `source_url` | Requested URL |
| `reference_date` | Requested or inferred date, if any |
| `retrieved_at` | UTC |
| `content_type` | |
| `encoding` | Optional |
| `filename` | |
| `http_status` | |
| `etag` / `last_modified` | Conditional GET metadata |
| `sha256` | Hex digest of stored bytes |
| `size_bytes` | |
| `storage_uri` | Object-store key or file URI |
| `ingestion_run_id` | FK |

Same `sha256` should reuse `storage_uri`. Metadata rows may still be created
per retrieval if that helps audit, but the blob is stored once.

### `ingestion_runs`

One row per CLI/workflow execution.

Record at least: provider, started_at, finished_at, requested_reference_date,
status, artifact counts, parse/normalize/insert/update/reject counts, warnings,
errors, duration, git_sha.

### `quality_events`

Per-record or per-run validation outcomes that did not necessarily abort the run.

Severity: `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

A single bad fund row must not fail an entire CVM month.

### `provider_status`

Latest health snapshot per provider: last success, last failure, last reference
date, consecutive failures, latest error.

### `dataset_publications`

Later. Phase 9 tracks generated Parquet files, manifests, checksums, schema
versions, and redistribution checks in **object storage** (`latest` JSON
pointers). A SQL ledger is not required until Phase 11 needs publish history
or R2 inventory.

---

## Instrument identity rules

Stable identity is a project invariant.

- Never use ticker as the universal primary key.
- Prefer ISIN, CNPJ / CNPJ_FUNDO_CLASSE, exchange security id, or
  `title_type + maturity_date` as asserted identifiers.
- Manual mappings, when needed, are explicit rows, not fuzzy name matching.

### CVM funds

Natural observation key:

```text
(CNPJ_FUNDO_CLASSE, ID_SUBCLASSE, DT_COMPTC)
```

- Pre-2023 files use `CNPJ_FUNDO`. Treat that as an alias of `CNPJ_FUNDO_CLASSE`.
- Empty `ID_SUBCLASSE` is stored as NULL.
- Punctuation is stripped for matching and preserved in display metadata if useful.

### Tesouro Direto

Identity is `title_type + maturity_date`.

- Marketing name (`Tesouro Prefixado`) maps to a bond code (`LTN`).
- NTN-B1 products (Renda+, Educa+) may also need `conversion_year`.
- Do not invent tickers as primary keys.

### B3 listed instruments

Prefer `B3_SECURITY_ID` from BVBG.028 plus ticker and ISIN as additional
identifiers. Ticker is a lookup alias.

### BCB

Series codes (`SGS:11`) identify market series, not instruments.

---

## Provenance

Every normalized observation should answer:

- which source
- which reference date
- when it was retrieved
- which price/value semantics
- which raw artifact
- which ingestion run
- which revision, if the source republished

Never fabricate missing values. Never present a stale observation as current
without exposing `reference_date` (and later `staleness_days`).

---

## Indexes (initial, justified)

Create only indexes with a query path:

- `instrument_identifiers (identifier_type, identifier_value)`
- `instrument_quotes (instrument_id, reference_date DESC)`
- `instrument_quotes (source_id, reference_date)`
- `market_series_observations (series_id, reference_date DESC)`
- `raw_artifacts (sha256)`

Do not partition `instrument_quotes` until volume justifies it (tens of millions
of rows). Document that threshold rather than partitioning early.

---

## API versus tables

Public consumers see resources and Parquet datasets, not SQL tables.

Desired public resources (when licensing allows):

- instruments
- quotes
- fund NAVs
- rates / series
- sources
- coverage
- datasets
