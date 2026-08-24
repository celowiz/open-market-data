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
| 6 | B3 derivatives official settlement | Planned |
| 7 | Yahoo local/POC provider, public exposure off | Planned |
| 8 | Brazilian credit public prints where available | Later in MVP window |
| 9 | Public Parquet + manifests for ODbL sources | Planned |
| 10 | Coverage engine and `/v1/coverage` | Planned |
| 11 | Scheduled GitHub Actions, Railway/Neon deploy, optional R2 | After core providers |

CVM remains the first functional vertical after Foundation.

### MVP success criteria (from project brief)

A contributor can clone the repo, `uv sync`, configure local PostgreSQL, run
migrations, ingest official sources, query FastAPI, inspect raw artifacts, and
see CI green. Public datasets respect licensing. Coverage can be computed for a
CSV universe.

---

## After MVP

These are recorded so they are not pulled into early phases:

- MkDocs Material on GitHub Pages
- Next.js Data Explorer on Vercel consuming FastAPI only
- Licensed global equity provider replacing Yahoo for public data
- Corporate actions
- Debenture / CRI / CRA fair-value sources beyond last trade
- ANBIMA, if terms allow a non-aggressive integration
- Python / R SDKs
- MCP server for agents
- API keys, usage dashboard, webhooks
- Historical lakehouse / ClickHouse if PostgreSQL is no longer enough

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
2. GitHub Actions CI (Phase 1)
3. GitHub Actions ingest schedules (Phase 11)
4. Neon + Railway for the official instance (Phase 11, user approval)
5. Cloudflare R2 only after R2 is enabled and approved
6. Custom domains `api.` / `data.` when a domain is chosen

Cloud services must not block local development.
