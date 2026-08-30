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
| 11 | Scheduled GitHub Actions, Dockerfile, deploy docs | Complete for artifacts. Neon is the serving DB (Free). FastAPI is live on Railway |
| 12 | Historical backfill CLI (CVM HIST, Tesouro full CSV, BCB ranges, B3/COTAHIST) | Complete (CLI + unit tests). Remaining operator work is historical backfill into **Neon** (B3 scratch 2024 slice running — not multi-year B3 history) |
| 13 | Next.js Data Explorer (`apps/explorer`; charts of Phase 12 series via `/v1` only) | Live at [open-market-data.vercel.app](https://open-market-data.vercel.app/) with `NEXT_PUBLIC_API_BASE_URL` pointing at the Railway origin |

CVM remains the first functional vertical after Foundation.

Phases 12 and 13 are a **paired track**: backfill populates PostgreSQL
history so `/v1` can return price series; the Explorer is how people look at
those series. Local PostgreSQL + `./data` + `next dev` is enough to develop.

**Operator hosting sequence:** Neon serving Postgres and Railway FastAPI are
live; Vercel already points `NEXT_PUBLIC_API_BASE_URL` at
`https://api-production-288d4.up.railway.app` (no trailing slash). Remaining
operator work is historical backfill into Neon, not provisioning Railway. See
[`DEPLOYMENT.md`](DEPLOYMENT.md).

### MVP success criteria (from project brief)

A contributor can clone the repo, `uv sync`, configure local PostgreSQL, run
migrations, ingest official sources, query FastAPI, inspect raw artifacts, and
see CI green. Public datasets respect licensing. Coverage can be computed for a
CSV universe.

Phase 12 extends that toward **multi-year history** in the serving database;
that load is still in progress (do not assume multi-year B3 history is present).
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
4. Neon as the official serving database (operator). Point ingest `DATABASE_URL`
   at Neon for live backfill; local Postgres remains the default for development
5. Historical backfill via `marketdata backfill` (Phase 12) **into Neon**.
   B3 scratch 2024 slice is the current operator load; this is remaining work,
   not a Railway provisioning gate
6. Local Next.js Explorer (`apps/explorer`) against `http://127.0.0.1:8000`
7. Vercel Explorer ([open-market-data.vercel.app](https://open-market-data.vercel.app/))
   — live, with `NEXT_PUBLIC_API_BASE_URL` pointing at the Railway origin
   (no trailing slash; visibility **config**, not secret)
8. Railway FastAPI (ADR-0005) — live at
   [https://api-production-288d4.up.railway.app](https://api-production-288d4.up.railway.app)
   (service `api`, project `open-market-data`). Do not put a connection string
   in this repository. Checklist for the already-hosted service:
   [`DEPLOYMENT.md`](DEPLOYMENT.md)
9. Cloudflare R2 only after R2 is enabled and approved (`uv sync --extra s3`)
10. Custom domains `api.` / `data.` when a domain is chosen

Cloud services must not block local development. Do not create additional
Railway projects in the same session as documentation-only work. Do not put
Python `PUBLIC_*` settings on the Vercel project.
