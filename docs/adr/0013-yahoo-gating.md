# ADR-0013: Programmatic gating for Yahoo (and similar unofficial sources)

- Status: Accepted
- Date: 2026-08-24

## Context

`yfinance` being Apache-2.0 does not license Yahoo's data. The platform must
allow local POC ingestion without accidentally publishing those series.

## Decision

Represent capability in source metadata and enforce it in API and dataset
publishers:

```text
ingestion_enabled: true   # optional for local/POC
public_api_enabled: false
public_dataset_enabled: false
redistribution_policy: UNKNOWN
is_official: false
```

Honor-system documentation is insufficient.

The same mechanism is reused for B3 on the official public instance until
redistribution is cleared.

## Alternatives

- **Docs-only warning:** too easy to leak via `/v1/quotes`.
- **Omit Yahoo entirely:** loses the original coverage-POC goal.

## Consequences

- Tests must prove Yahoo (or a fake restricted source) cannot appear on public
  routes when flags are off.

## Why before Phase 7 (design in Phase 1)

Foundation should store the flags even if Yahoo is unimplemented.
