# ADR-0014: Default-deny public redistribution of B3 data

- Status: Accepted
- Date: 2026-08-24

## Context

B3 EOD files are reachable from public websites, and community libraries
download them. B3 Market Data policy (rules highlighted around 2026-01-01)
classifies EOD as Market Data. Distribution and productization generally need
B3 licenses. This is **not** the same situation as CVM/Tesouro/BCB ODbL.

## Decision

- **Ingestion** of B3 EOD may be implemented for local and self-hosted use.
- **Official public API and public Parquet default to off**
  (`public_api_enabled=false`, `public_dataset_enabled=false`,
  `redistribution_policy=UNKNOWN` or `NO_REDISTRIBUTION`).
- Do not assume "public download URL means we may republish".

Revisit only with a documented license, counsel, or written B3 permission.

## Alternatives

- **Treat as open data:** legal risk for a public dataset/API product.
- **Skip B3 entirely:** would gut Brazilian equity/derivative coverage.

## Consequences

- Coverage reports on the official instance may count B3 as found locally
  while still omitting it from public endpoints.
- Phase 5 can proceed on ingestion; Phase 9 must skip B3 until this ADR changes.

## Why before Phase 5 public exposure

This is **blocking for publication**, not for parser design.
