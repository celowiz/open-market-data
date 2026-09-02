from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from marketdata import __version__
from marketdata.api.deps import bind_database, dispose_database
from marketdata.api.routes.coverage import router as coverage_router
from marketdata.api.routes.datasets import router as datasets_router
from marketdata.api.routes.events import router as events_router
from marketdata.api.routes.funds import router as funds_router
from marketdata.api.routes.health import router as health_router
from marketdata.api.routes.hooks import router as hooks_router
from marketdata.api.routes.instruments import router as instruments_router
from marketdata.api.routes.lending import router as lending_router
from marketdata.api.routes.macro import router as macro_router
from marketdata.api.routes.quotes import router as quotes_router
from marketdata.api.routes.series import router as series_router
from marketdata.api.routes.sources import router as sources_router
from marketdata.config import get_settings
from marketdata.providers.bootstrap import register_default_providers


def _cors_origins(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    bind_database(app)
    try:
        yield
    finally:
        dispose_database(app)


def create_app() -> FastAPI:
    register_default_providers()
    settings = get_settings()
    docs_url = "/docs" if settings.api_docs_enabled else None
    redoc_url = "/redoc" if settings.api_docs_enabled else None
    openapi_url = "/openapi.json" if settings.api_docs_enabled else None
    app = FastAPI(
        title="Open Market Data",
        version=__version__,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    origins = _cors_origins(settings.cors_allowed_origins)
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET"],
            allow_headers=["*"],
        )
    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(sources_router, prefix=settings.api_v1_prefix)
    app.include_router(funds_router, prefix=settings.api_v1_prefix)
    app.include_router(quotes_router, prefix=settings.api_v1_prefix)
    app.include_router(series_router, prefix=settings.api_v1_prefix)
    app.include_router(coverage_router, prefix=settings.api_v1_prefix)
    app.include_router(datasets_router, prefix=settings.api_v1_prefix)
    app.include_router(instruments_router, prefix=settings.api_v1_prefix)
    app.include_router(lending_router, prefix=settings.api_v1_prefix)
    app.include_router(events_router, prefix=settings.api_v1_prefix)
    app.include_router(macro_router, prefix=settings.api_v1_prefix)
    app.include_router(hooks_router, prefix=settings.api_v1_prefix)
    bind_database(app)
    return app


app = create_app()
