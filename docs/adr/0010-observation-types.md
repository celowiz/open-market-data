# ADR-0010: Separate quotes, series, and curve points

- Status: Accepted
- Date: 2026-08-24

## Context

Treating CDI, PETR4 close, fund NAV, and DI curve vertices as one `quotes`
table destroys semantics and identity.

## Decision

Persist three observation kinds:

1. `instrument_quotes` — instruments with identifiers
2. `market_series_observations` — official series such as Selic, CDI, PTAX
3. `curve_points` — deferred until a curve provider exists

Shared provenance fields (source, artifact, run, revision) are parallel, not
forced into a single polymorphic table in MVP.

## Alternatives

- **Single generic observation table:** simpler schema, weaker invariants.
- **Provider-specific tables only:** blocks a coherent public API.

## Consequences

- BCB Phase 4 must not insert CDI into `instrument_quotes`.
- API resources differ: `/v1/quotes/...` versus `/v1/series/...`.

## Why before Phase 1

Foundation migrations must create the right tables.
