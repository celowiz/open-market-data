from collections.abc import Generator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from marketdata.config import get_settings
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.object_store import ObjectStorage, build_object_storage


def get_db() -> Generator[Session, None, None]:
    settings = get_settings()
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
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
