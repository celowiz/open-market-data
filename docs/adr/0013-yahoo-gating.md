# ADR-0013: Programmatic gating for Yahoo (and similar unofficial sources)

- Status: Accepted (datasets). Operational exception 2026-08-24: public API
  follows `public_api_enabled` only, so Yahoo quotes may appear on `/v1` while
  `redistribution_policy` stays `UNKNOWN`. `public_dataset_enabled` remains false.
- Date: 2026-08-24

## Context

`yfinance` being Apache-2.0 does not license Yahoo's data. The platform must
allow local POC ingestion without accidentally publishing those series.

## Decision

Represent capability in source metadata and enforce it in API and dataset
publishers:

```text
ingestion_enabled: true   # optional for local/POC
public_api_enabled: true  # temporary operational choice for local/API testing
public_dataset_enabled: false
redistribution_policy: UNKNOWN
is_official: false
```

Honor-system documentation is insufficient.

The public API gate currently honors `public_api_enabled` only. Redistribution
policy still blocks Parquet / public datasets. Re-tighten the API gate before
exposing an official public instance.

The same mechanism is reused for B3 on the official public instance until
redistribution is cleared.

## Alternatives

- **Docs-only warning:** too easy to leak via `/v1/quotes`.
- **Omit Yahoo entirely:** loses the original coverage-POC goal.

## Consequences

- Tests must prove a source with `public_api_enabled=false` cannot appear on
  public routes. Yahoo is currently served when the flag is on.

## Why before Phase 7 (design in Phase 1)

Foundation should store the flags even if Yahoo is unimplemented.
