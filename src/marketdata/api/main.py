from fastapi import FastAPI

from marketdata import __version__
from marketdata.api.routes.funds import router as funds_router
from marketdata.api.routes.health import router as health_router
from marketdata.api.routes.quotes import router as quotes_router
from marketdata.api.routes.series import router as series_router
from marketdata.api.routes.sources import router as sources_router
from marketdata.config import get_settings
from marketdata.providers.bootstrap import register_default_providers


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
    )
    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(sources_router, prefix=settings.api_v1_prefix)
    app.include_router(funds_router, prefix=settings.api_v1_prefix)
    app.include_router(quotes_router, prefix=settings.api_v1_prefix)
    app.include_router(series_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
