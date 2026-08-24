# ADR-0005: Railway for official API hosting

- Status: Accepted for official deployment; not implemented in early phases
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

## Why document now

Stops frontend-platform drift during Foundation.
