# Deployment

Official hosting (Railway, Neon, optional Cloudflare R2, GitHub Actions ingest
schedules) is **Phase 11** of [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

Historical population of that database (`marketdata backfill`) is **Phase 12**.
The Next.js Data Explorer on Vercel is **Phase 13** and talks only to FastAPI.

Until then:

- Run the API with `uv run uvicorn marketdata.api.main:app`
- Use local PostgreSQL via `DATABASE_URL` (or a Neon **dev** branch if you
  already have one; this is not Phase 11 production)
- Use filesystem object storage (`OBJECT_STORAGE_BACKEND=local`)
- Daily smoke ingest: `uv run marketdata ingest <provider> --date YYYY-MM-DD`
- Public Parquet (ODbL sources only): set `PUBLIC_DATASET_PUBLICATION_ENABLED=true`
  then `uv run marketdata publish datasets --date YYYY-MM-DD`. Files land under
  `data/public/...` on the local filesystem backend. Cloudflare R2 remains
  Phase 11.

Do not create paid cloud resources without explicit approval.
Do not treat a one-day ingest as a full-history load (see Phase 12).
