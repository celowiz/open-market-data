# Roadmap

This roadmap is a planning view. Execution order and acceptance criteria live in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

---

## MVP

The MVP answers, with real public data:

> What percentage of an arbitrary instrument universe can be priced daily from
> public and free sources?

It also publishes an auditable local/self-hosted pipeline and a versioned API
for sources that may be redistributed.

### Milestones

| Phase | Milestone | Status |
|---|---|---|
| 0 | Seed documentation, ADRs, implementation plan | Complete |
| 1 | Foundation: package, domain, PostgreSQL, object store, CLI/API skeletons, CI | Complete |
| 2 | CVM Fund NAV end-to-end | Complete |
| 3 | Tesouro Direto quotes | Complete |
| 4 | BCB PTAX / Selic / CDI series | Complete |
| 5 | B3 equities ingestion (`API_ONLY` public quotes, no Parquet) | Complete |
| 6 | B3 derivatives official settlement | Complete |
| 7 | Yahoo local/POC provider, public exposure off | Complete |
| 8 | Brazilian credit public prints where available | Complete |
| 9 | Public Parquet + manifests for ODbL sources | Complete |
| 10 | Coverage engine and `/v1/coverage` | Complete |
| 11 | Scheduled GitHub Actions, Dockerfile, deploy docs (no cloud projects created) | Complete for artifacts, not provisioned |
| 12 | Historical backfill CLI (CVM HIST, Tesouro full CSV, BCB ranges, B3/COTAHIST) | Complete (CLI + unit tests; operator live load is local) |
| 13 | Next.js Data Explorer (`apps/explorer`; charts of Phase 12 series via `/v1` only) | Complete (local; Vercel not provisioned) |

CVM remains the first functional vertical after Foundation.

Phases 12 and 13 are a **paired track**: backfill populates PostgreSQL
history so `/v1` can return price series; the Explorer is how people look at
those series. Official Neon/Railway/Vercel hosting remains an operator step
with explicit approval. Local PostgreSQL + `./data` + `next dev` is enough.

### MVP success criteria (from project brief)

A contributor can clone the repo, `uv sync`, configure local PostgreSQL, run
migrations, ingest official sources, query FastAPI, inspect raw artifacts, and
see CI green. Public datasets respect licensing. Coverage can be computed for a
CSV universe.

Phase 12 extends that to **multi-year history** in the serving database.
Phase 13 adds a browser Explorer on top of the same API.

---

## After MVP

These are recorded so they are not pulled into early phases:

- MkDocs Material on GitHub Pages
- Licensed global equity provider replacing Yahoo for public data
- Corporate actions
- Debenture / CRI / CRA fair-value sources beyond last trade
- ANBIMA, if terms allow a non-aggressive integration
- Python / R SDKs
- MCP server for agents
- API keys, usage dashboard, webhooks
- Historical lakehouse / ClickHouse if PostgreSQL is no longer enough

Next.js Data Explorer moved to **Phase 13** (no longer an unscheduled after-MVP
item). It still must not query PostgreSQL directly.

---

## Explicitly not in MVP

- Bloomberg clone or trading terminal
- Real-time market data, WebSockets, tick database
- Authentication and billing
- Portfolio accounting / OMS / custodian reconciliation
- Airflow, Kafka, Kubernetes, Celery, Redis
- Supabase
- Direct public SQL access

---

## Infrastructure sequence

1. Local PostgreSQL + filesystem object storage (required from Phase 1)
2. GitHub Actions CI (Phase 1) and Explorer CI (`.github/workflows/explorer.yml`)
3. GitHub Actions ingest schedules and `backfill.yml` dispatch (Phase 11 artifacts)
4. Neon + Railway for the official instance (operator approval; **not created**
   in Phase 11)
5. Historical backfill via `marketdata backfill` (Phase 12) into local Postgres
   or a Neon URL the operator already has
6. Local Next.js Explorer (`apps/explorer`) against FastAPI; Vercel later with
   approval
7. Cloudflare R2 only after R2 is enabled and approved (`uv sync --extra s3`)
8. Custom domains `api.` / `data.` when a domain is chosen

Cloud services must not block local development.
