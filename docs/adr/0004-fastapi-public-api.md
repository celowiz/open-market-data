# ADR-0004: FastAPI for the public API

- Status: Accepted
- Date: 2026-08-24

## Context

The public product is a versioned HTTP API with OpenAPI docs, decimal-safe
JSON, and no live provider calls during requests.

## Decision

Use **FastAPI** with `/v1` from the first skeleton. OpenAPI remains enabled.
The app must run with stock `uvicorn` anywhere, including later Railway.

## Alternatives

- **Flask / Django Ninja:** possible, but FastAPI is the brief's choice and
  matches typing + OpenAPI needs.
- **Expose PostgREST / Supabase:** rejected; we need domain provenance and
  redistribution gates, not table CRUD.
- **Vercel Python:** rejected for the data API; Vercel is reserved for a future
  Next.js explorer.

## Consequences

- API schemas are separate from SQLAlchemy models.
- No `/query?sql=` endpoint.

## Why before Phase 1

The health-check skeleton is part of Foundation.
