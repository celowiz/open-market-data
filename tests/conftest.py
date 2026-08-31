import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from marketdata.config import get_settings
from marketdata.storage.database import create_db_engine

_ENGINE: Engine | None = None


def _truncate_engine() -> Engine | None:
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    settings = get_settings()
    if not settings.database_url:
        return None
    _ENGINE = create_db_engine(settings)
    return _ENGINE


def _truncate_public_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
                  AND backend_type = 'client backend'
                """
            )
        )
        tables = connection.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename <> 'alembic_version'
                """
            )
        ).fetchall()
        names = [row[0] for row in tables]
        if not names:
            return
        quoted = ", ".join(f'"{name}"' for name in names)
        connection.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Empty serving tables before each @pytest.mark.db test.

    Session rollback is not enough: ingest/API tests ``commit()`` and TestClient
    uses a separate session. Truncate keeps schema, indexes, and
    ``uq_instrument_quotes_identity``. Alembic stays applied for the run.

    Other client backends are terminated first so pooled TestClient connections
    cannot hold a lock and stall TRUNCATE.
    """
    if item.get_closest_marker("db") is None:
        return
    engine = _truncate_engine()
    if engine is not None:
        _truncate_public_tables(engine)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    global _ENGINE
    if _ENGINE is not None:
        _ENGINE.dispose()
        _ENGINE = None
