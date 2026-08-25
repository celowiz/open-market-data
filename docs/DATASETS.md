# Public Parquet datasets

Phase 9 publishes curated Parquet snapshots for sources that pass **both**
`redistribution_policy ∈ {PUBLIC, PUBLIC_WITH_ATTRIBUTION}` and
`public_dataset_enabled`. That is CVM, Tesouro, and BCB (ODbL) in the current
catalog. B3 (`API_ONLY`) and Yahoo (`UNKNOWN`) are never published.

Apache-2.0 licenses **this repository's code**, not the Parquet files. Published
files are derived databases under **ODbL 1.0**. Share-alike applies to the
derived database. Cite the originating portal when you redistribute.

Publication is opt-in. `PUBLIC_DATASET_PUBLICATION_ENABLED` defaults to `false`.
Set it to `true` only when you intend to write objects. Source flags remain the
legal gate; the global flag is not a substitute for skipping B3/Yahoo.

## Catalog

One Parquet file per name per snapshot (not hive `source=/year=/month=`). Mix
only ODbL sources in the same file. `source` is a column so users can filter.

| Name | Contents |
|---|---|
| `sources` | `sources` rows that pass the dataset gate (`cvm`, `tesouro`, `bcb`). Not the same as `GET /v1/sources`, which can include B3 `API_ONLY`. |
| `instruments` | Instrument masters that have at least one quote from a dataset-eligible source (CVM funds, Tesouro titles). No B3/Yahoo-only masters. |
| `quotes` | `instrument_quotes` from eligible sources (CVM `FUND_NAV`, Tesouro `PU_BASE` / `BID_PU` / `ASK_PU` / `YIELD` / `INDICATIVE`). Every stored `price_type` is kept. No PETR4 `LAST`, DI1 `OFFICIAL_SETTLEMENT`, credit `LAST`, or Yahoo `CLOSE`. |
| `fund_nav` | The quotes extract filtered to `price_type = FUND_NAV`, with CNPJ / subclass columns when identifiers exist. Duplication with `quotes` is expected. |
| `rates` | `market_series` + observations (CDI / Selic / PTAX). Not mixed into `quotes`. |

Empty catalogs are skipped: that dataset's `latest` pointer is not moved.

## `--date` semantics

`--date YYYY-MM-DD` is the **snapshot identifier**, not
`WHERE reference_date = :date`. Publish writes **all eligible rows currently in
PostgreSQL**. Manifest `reference_period` is `{start, end}` from min/max
`reference_date` in that file. A partial serving snapshot is fine; Phase 12
backfill is what makes files multi-year.

## Object keys

Local filesystem object storage (default `LOCAL_STORAGE_PATH=./data`):

```text
public/datasets/{name}/schema_v1/{YYYY-MM-DD}.parquet
public/manifests/{name}/{YYYY-MM-DD}.json
public/manifests/{name}-latest.json
```

`latest` is JSON only. Never write Parquet to a `latest` key. Hive partitions
are deferred to a later `schema_version` after Phase 12. Cloudflare R2 is not
required; Phase 11 may add an S3-compatible backend behind the same interface.

## CLI

```bash
# fail-closed unless you opt in
export PUBLIC_DATASET_PUBLICATION_ENABLED=true
export DATABASE_URL=postgresql://...

uv run marketdata publish datasets --date 2026-08-21
uv run marketdata publish datasets --date 2026-08-21 --dry-run
uv run marketdata publish datasets --date 2026-08-21 --dataset quotes
```

- `--dry-run` extracts and validates, then prints counts/keys without writing.
- Repeatable `--dataset` limits the catalog; default is all five names.
- `PUBLIC_DATASET_FORMAT` must be `parquet` (CSV is not implemented).
- Best-effort per dataset: a quotes failure does not block rates. Exit code 1
  if any requested dataset **failed** (empty skips are not failures).
- Re-running the same `--date` overwrites the dated objects and points `latest`
  at them.

The publisher reads PostgreSQL and writes object storage. It does not call
CVM, B3, Yahoo, or BCB HTTP APIs.

## API

```text
GET /v1/datasets
GET /v1/datasets/{name}
```

Listing only: manifests with `object_key`, `sha256`, `row_count`, license, and
`url` when `PUBLIC_DATA_BASE_URL` is set. FastAPI does **not** stream Parquet.
`{name}` must be one of the five catalog names.

## How to read local files

```python
import polars as pl
from pathlib import Path

root = Path("./data")  # LOCAL_STORAGE_PATH
df = pl.read_parquet(root / "public/datasets/quotes/schema_v1/2026-08-21.parquet")
```

Value columns use `Decimal(38, 16)`, matching `NUMERIC(38, 16)`. Do not recast
them to IEEE floats.

## Attribution (ODbL)

Every manifest includes `license: ODbL-1.0`,
`redistribution_policy: PUBLIC_WITH_ATTRIBUTION`, and attribution snippets for
the sources present in that file. Current snippets:

- CVM: data from Portal de Dados Abertos CVM, https://dados.cvm.gov.br/
- Tesouro: data from Tesouro Transparente / Tesouro Nacional
- BCB: data from Banco Central do Brasil open data / SGS / PTAX

See [`DATA_LICENSES.md`](../DATA_LICENSES.md) and [`LICENSING.md`](LICENSING.md).
