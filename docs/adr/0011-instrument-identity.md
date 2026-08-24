# ADR-0011: Stable instrument identity via UUID plus identifier table

- Status: Accepted
- Date: 2026-08-24

## Context

Tickers collide, change, and are venue-specific. CVM moved from `CNPJ_FUNDO`
to `CNPJ_FUNDO_CLASSE`. Tesouro identity is title type plus maturity.

## Decision

- Canonical key: UUID `instruments.id`
- External keys live in `instrument_identifiers` with type, value, source, and
  optional validity window
- Resolver accepts ticker, ISIN, CNPJ (with or without punctuation), B3 ids,
  Yahoo symbols, and composite treasury keys

Do not use ticker as the primary key.

## Alternatives

- **Natural key only (ISIN/CNPJ):** fails when an identifier is missing or
  reused over time.
- **Source-native IDs as PK:** cannot merge the same economic instrument from
  two sources later.

## Consequences

- Mapping errors become first-class (`MAPPING_ERROR` in coverage later).
- Fund subclass is part of identity when `ID_SUBCLASSE` is present.

## Why before Phase 1

Schema and API path design depend on this.
