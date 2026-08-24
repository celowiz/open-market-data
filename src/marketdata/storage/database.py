from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from marketdata.config import Settings, get_settings
from marketdata.storage.urls import normalize_database_url


def create_db_engine(settings: Settings | None = None) -> Engine:
    cfg = settings or get_settings()
    if not cfg.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return create_engine(
        normalize_database_url(cfg.database_url),
        pool_size=cfg.database_pool_size,
        max_overflow=cfg.database_max_overflow,
        pool_timeout=cfg.database_pool_timeout,
        future=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def session_scope(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
