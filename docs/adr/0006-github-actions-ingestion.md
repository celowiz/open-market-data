# ADR-0006: GitHub Actions for scheduled ingestion

- Status: Accepted for official orchestration; CLI remains the real runner
- Date: 2026-08-24

## Context

MVP ingestion is daily/EOD, not a streaming platform. The repository is public
and can use standard GitHub-hosted runners.

## Decision

Official scheduled ingestion uses **GitHub Actions** invoking the project CLI.
Do not introduce Airflow, Celery, Kafka, or Redis for MVP.

Every ingest workflow should support `workflow_dispatch` for reruns and
backfills.

## Alternatives

- **Airflow / Prefect:** operationally heavy for a small open-source repo.
- **In-process FastAPI cron:** couples serving and fetching; worse failure
  isolation.
- **Self-hosted workers only:** allowed for self-host, not required for official
  MVP.

## Consequences

- Schedules are per provider (publication times differ); UTC cron must be
  documented against America/Sao_Paulo.
- Actions must not hammer sources: concurrency limits, retries, checkpoints.

## Why document now

Keeps Foundation free of job-queue infrastructure.
