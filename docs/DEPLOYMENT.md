# Deployment

Official hosting (Railway, Neon, optional Cloudflare R2, GitHub Actions ingest
schedules) is **Phase 11** of [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

Until then:

- Run the API with `uv run uvicorn marketdata.api.main:app`
- Use local PostgreSQL via `DATABASE_URL`
- Use filesystem object storage (`OBJECT_STORAGE_BACKEND=local`)

Do not create paid cloud resources without explicit approval.
