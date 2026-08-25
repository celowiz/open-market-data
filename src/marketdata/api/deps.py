from collections.abc import Generator
from typing import cast

from fastapi import HTTPException
from sqlalchemy.orm import Session

from marketdata.config import get_settings
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


def get_db() -> Generator[Session, None, None]:
    settings = get_settings()
    if not settings.database_url:
        session = cast(Session, _UnavailableSession())
        try:
            yield session
        finally:
            session.close()
        return
    factory = create_session_factory(create_db_engine(settings))
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
