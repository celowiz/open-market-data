from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine

from marketdata.api.deps import bind_database
from marketdata.config import get_settings

router = APIRouter()


_READY_503 = {
    503: {
        "description": (
            "Readiness check failed: DATABASE_URL is missing or Postgres did not answer SELECT 1."
        )
    }
}


def ping_database(engine: Engine) -> None:
    """Run `SELECT 1` without taking a lock."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def database_readiness(request: Request) -> Any:
    """Ping PostgreSQL; 200 when SELECT 1 succeeds, 503 otherwise."""
    settings = get_settings()
    if not settings.database_url:
        return JSONResponse(
            status_code=503,
            content={"status": "unready", "detail": "DATABASE_URL is not configured"},
        )
    try:
        bind_database(request.app, settings)
        engine = getattr(request.app.state, "db_engine", None)
        if engine is None:
            raise RuntimeError("database engine is not bound")
        ping_database(engine)
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unready", "detail": "database ping failed"},
        )
    return {"status": "ok"}


@router.get("/health", responses=_READY_503)
def health(
    request: Request,
    ready: bool = Query(
        default=False,
        description=(
            "If true, ping PostgreSQL with SELECT 1. Default liveness does not touch the database."
        ),
    ),
) -> Any:
    if not ready:
        return {"status": "ok"}
    return database_readiness(request)


@router.get(
    "/ready",
    responses=_READY_503,
    summary="Readiness check",
    description=(
        "Same semantics as GET /v1/health?ready=1: SELECT 1 against PostgreSQL. "
        "Path-only for hosts that cannot put a query string in the probe path."
    ),
)
def ready(request: Request) -> Any:
    return database_readiness(request)
