# ADR-0012: CVM Fund NAV as the first functional provider

- Status: Accepted
- Date: 2026-08-24

## Context

The brief suggested CVM → fetch → raw → parse → normalize → PostgreSQL →
FastAPI as the first vertical. Planning re-validated official CVM files.

CVM is official, ZIP+CSV structured, ODbL-redistributable, and exercises
schema drift, revisions, Decimal NAV, and provenance.

Tesouro adds multiple price types per day. BCB is a different domain
(series, not instruments). B3 has redistribution risk and XML complexity.

## Decision

After Foundation, implement **CVM Informe Diário / VL_QUOTA** first.

Tesouro and BCB follow and may run in parallel with each other, not with CVM.

## Alternatives

- **Tesouro first:** attractive CSV, but weaker test of fund identity and
  schema eras.
- **BCB first:** smallest HTTP client, does not prove instrument quotes.
- **B3 first:** highest product value for equities, highest legal and format
  risk.

## Consequences

- Phase 2 Definition of Done includes a real `GET /v1/funds/{cnpj}/quotes`
  response and `marketdata explain`.

## Why now

Locks the MVP sequence so later phases are not started first.
