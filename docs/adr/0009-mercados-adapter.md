# ADR-0009: mercados as an adapter-only dependency

- Status: Accepted for Phase 2 evaluation; fallback is direct httpx
- Date: 2026-08-24

## Context

`PythonicCafe/mercados` is the strongest Brazilian official-data client
(LGPL-3.0, pre-1.0). The domain must not depend on its classes. CVM current
files are monthly ZIPs; several other OSS clients still hit broken CSV URLs.

## Decision

Prefer **mercados behind provider adapters** when it correctly fetches current
official files. If CVM ZIP support is missing or unstable, `CvmProvider` will
use `httpx` directly and still isolate that code in `providers/`.

Never `from mercados...` outside `providers/`.

Ship LGPL notices and keep the library replaceable.

## Alternatives

- **Reimplement every fetcher:** more control, more maintenance.
- **Depend on mercados in domain code:** rejected.
- **Vendor/fork mercados into the tree:** LGPL compliance burden; avoided.

## Consequences

- Phase 2 starts with a short spike: can mercados download INF_DIARIO ZIPs?
- Pre-1.0 API breakage is expected; pin versions.

## Why before Phase 2

This is the remaining **blocking packaging question** before CVM implementation
(LGPL + Apache). Documentation is required even if httpx is used instead.
