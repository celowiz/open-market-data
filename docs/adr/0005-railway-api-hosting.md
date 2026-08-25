# ADR-0005: Railway for official API hosting

- Status: Accepted for official deployment; Railway project not created until
  Neon serving tables are backfilled
- Date: 2026-08-24

## Context

The official FastAPI process needs a conventional long-running host. Vercel is
a poor fit for Python ingestion-adjacent APIs. A Railway account exists; no
project should be created until Phase 11 with approval.

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
- Provisioning order: populate Neon with `marketdata backfill` first, then
  create the Railway FastAPI service, then set Vercel
  `NEXT_PUBLIC_API_BASE_URL` to that origin. Checklist:
  [`DEPLOYMENT.md`](../DEPLOYMENT.md#next-operator-step-railway-fastapi-after-neon-backfill).

## Why document now

Stops frontend-platform drift during Foundation.
