# ADR-0003: Object storage behind an interface, filesystem first

- Status: Accepted
- Date: 2026-08-24

## Context

Raw artifacts and later Parquet datasets must not live in PostgreSQL.
Cloudflare R2 is the preferred production object store but is **not enabled**.
Local development must not require Cloudflare credentials.

## Decision

Define a small `ObjectStorage` protocol (`store`, `retrieve`, `exists`, and
minimal metadata). Implement `LocalFileObjectStorage` in Phase 1. Add
`S3ObjectStorage` later for R2 or any S3-compatible backend.

Blob content and `raw_artifacts` metadata remain separate.

## Alternatives

- **PostgreSQL BYTEA / large objects:** rejected; files are large and immutable.
- **Require R2 from day one:** blocks local and self-host development.
- **MinIO-only:** extra moving part for MVP; S3 interface can target MinIO later
  if a contributor wants it.

## Consequences

- `OBJECT_STORAGE_BACKEND=local` is the default.
- Domain and providers never import boto3/R2 SDKs directly.

## Why before Phase 1

CVM ingestion in Phase 2 needs a working raw store.
