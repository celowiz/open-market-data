# Portable FastAPI image (ADR-0005). Do not bake credentials or .env.
# Default command serves the API only — do not run ingest in this container.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 1000 --create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations

RUN mkdir -p /app/data && chown app:app /app/data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOCAL_STORAGE_PATH=/app/data

USER app

EXPOSE 8000

# Railway injects PORT. Bind all interfaces; do not use API_HOST from settings.
CMD ["sh", "-c", "exec uvicorn marketdata.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
