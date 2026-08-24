# ADR-0014: Default-deny public redistribution of B3 data

- Status: Accepted (datasets). Operational exception 2026-08-24: public API
  may serve B3 quotes with `redistribution_policy=API_ONLY` and
  `public_api_enabled=true`. `public_dataset_enabled` remains false.
- Date: 2026-08-24

## Context

B3 EOD files are reachable from public websites, and community libraries
download them. B3 Market Data policy (rules highlighted around 2026-01-01)
classifies EOD as Market Data. Distribution and productization generally need
B3 licenses. This is **not** the same situation as CVM/Tesouro/BCB ODbL.

## Decision

- **Ingestion** of B3 EOD may be implemented for local and self-hosted use.
- **Official public Parquet stays off.** Quotes may appear on the public API
  under `API_ONLY` (`public_api_enabled=true`, `public_dataset_enabled=false`).
  Bulk republish still requires a license, counsel, or written B3 permission.

## Alternatives

- **Treat as open data:** legal risk for a public dataset/API product.
- **Skip B3 entirely:** would gut Brazilian equity/derivative coverage.

## Consequences

- Public API may list B3 quotes (`API_ONLY`); public Parquet must still skip B3.
- Phase 9 must skip B3 until a license or written permission is confirmed.

## Why before Phase 5 public exposure

This is **blocking for publication**, not for parser design.
