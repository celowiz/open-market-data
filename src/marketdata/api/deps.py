from collections.abc import Generator
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.orm import Session

from marketdata.config import Settings, get_settings
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.object_store import ObjectStorage, build_object_storage

_DATABASE_UNAVAILABLE = "DATABASE_URL is not configured"


class _UnavailableSession:
    """Stand-in so request validation can run before a missing DATABASE_URL 503."""

    def close(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def __getattr__(self, _name: str) -> None:
        raise HTTPException(status_code=503, detail=_DATABASE_UNAVAILABLE)


def bind_database(app: FastAPI, settings: Settings | None = None) -> None:
    """Attach a process-lifetime engine/session factory to the FastAPI app."""
    if getattr(app.state, "db_engine", None) is not None:
        return
    cfg = settings or get_settings()
    if not cfg.database_url:
        app.state.db_engine = None
        app.state.session_factory = None
        return
    engine = create_db_engine(cfg)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)


def dispose_database(app: FastAPI) -> None:
    engine = getattr(app.state, "db_engine", None)
    if engine is not None:
        engine.dispose()
    app.state.db_engine = None
    app.state.session_factory = None


def get_db(request: Request) -> Generator[Session, None, None]:
    settings = get_settings()
    if not settings.database_url:
        session = cast(Session, _UnavailableSession())
        try:
            yield session
        finally:
            session.close()
        return
    bind_database(request.app, settings)
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        session = cast(Session, _UnavailableSession())
        try:
            yield session
        finally:
            session.close()
        return
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_object_storage() -> ObjectStorage:
    return build_object_storage()
