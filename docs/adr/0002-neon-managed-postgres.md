# ADR-0002: Neon as the official managed PostgreSQL

- Status: Accepted for official deployment; not required for development
- Date: 2026-08-24

## Context

The official public instance needs hosted PostgreSQL. Supabase was considered
because it bundles Auth, storage, and PostgREST. This project does not need
those products for MVP.

## Decision

Use **Neon** for the official managed PostgreSQL when deployment is approved.
The application continues to use a generic `DATABASE_URL` and standard
PostgreSQL. Local development uses any PostgreSQL.

Do not create Neon **production** resources until Phase 11 with explicit
approval. A Neon **dev branch** may be used earlier via `DATABASE_URL` (for
example Phase 12 backfill) without treating that as official deploy.

## Alternatives

- **Supabase:** Auth/Realtime unused; PostgREST would bypass our domain API;
  vendor coupling.
- **Railway PostgreSQL / RDS / self-hosted:** valid self-host options; Neon is
  the official instance choice, not a domain dependency.
- **Neon-specific APIs in app code:** rejected to preserve portability.

## Consequences

- No `neon` SDK in application code.
- Branching/dev databases are an ops convenience, not a schema feature.

## Why document now

Prevents accidental Supabase or Neon lock-in during Foundation.
