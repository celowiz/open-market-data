# ADR-0005: Railway for official API hosting

- Status: Accepted. Official FastAPI on Railway is live (2026-08-30).
- Date: 2026-08-24

## Context

The official FastAPI process needs a conventional long-running host. Vercel is
a poor fit for Python ingestion-adjacent APIs. Official hosting is Railway
(project created after Phase 11 approval; live 2026-08-30).

## Decision

Official API hosting is **Railway**, via Dockerfile / `uvicorn`, not a
Railway-specific runtime API.

Self-hosters may run the same image or `uvicorn` anywhere.

## Alternatives

- **Fly.io / Render / Cloud Run:** valid alternatives; not the official choice.
- **Vercel as FastAPI host:** rejected.
- **Kubernetes:** premature.

## Consequences

- Dockerfile should be portable.
- Railway MCP may be used later for ops; app code stays host-agnostic.
- Provisioning order was Neon backfill, then Railway FastAPI, then Vercel
  `NEXT_PUBLIC_API_BASE_URL`. The official instance is live; remaining work is
  Neon historical backfill. Checklist:
  [`DEPLOYMENT.md`](../DEPLOYMENT.md#remaining-operator-work-historical-backfill-into-neon).

## Why document now

Stops frontend-platform drift during Foundation.
