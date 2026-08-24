# ADR-0008: Apache License 2.0 for source code

- Status: Accepted, pending Phase 1 LICENSE file and NOTICE for LGPL deps
- Date: 2026-08-24

## Context

The project is public and intended for reuse. Some candidate libraries are
copyleft (LGPL mercados, AGPL securo/OpenBB, GPL amgsnt/cvm).

## Decision

License **our** source as **Apache-2.0**.

- Do not take AGPL or GPL dependencies.
- LGPL-3.0 `mercados` may be an optional/runtime adapter dependency with
  notices and replacement rights. See ADR-0009.
- Data remains under each source's terms (`DATA_LICENSES.md`).

## Alternatives

- **MIT:** similar permissive outcome; Apache-2.0 adds patent language matching
  the brief.
- **AGPL for our API:** would chill commercial self-host and is unnecessary.
- **Refuse all LGPL:** forces reimplementing CVM/B3 fetchers; acceptable fallback
  if mercados packaging becomes a problem.

## Consequences

- Add `LICENSE` in Phase 1.
- Add `NOTICE` when mercados is introduced (Phase 2).

## Why before implementation

Incompatible licenses cannot be discovered after code lands.
