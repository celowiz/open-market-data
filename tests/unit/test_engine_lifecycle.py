from collections.abc import Iterator
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from marketdata.api.deps import bind_database, dispose_database, get_db
from marketdata.api.main import create_app
from marketdata.config import Settings
from marketdata.storage.database import DEFAULT_POOL_RECYCLE_SECONDS, create_db_engine


def _settings_with_url() -> Settings:
    return Settings(_env_file=None, database_url="postgresql://u:p@localhost/db")


def _request_for(app) -> Request:
    return Request(
        {
            "type": "http",
            "app": app,
            "headers": [],
            "method": "GET",
            "path": "/",
            "scheme": "http",
            "query_string": b"",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )


def _consume_session(request: Request):
    gen: Iterator = get_db(request)
    session = next(gen)
    try:
        next(gen)
    except StopIteration:
        pass
    return session


def test_create_db_engine_enables_pre_ping_and_neon_recycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_create_engine(url: str, **kwargs: object) -> MagicMock:
        captured["url"] = url
        captured.update(kwargs)
        return MagicMock(name="engine")

    monkeypatch.setattr("marketdata.storage.database.create_engine", fake_create_engine)
    create_db_engine(_settings_with_url())
    assert captured["pool_pre_ping"] is True
    assert captured["pool_recycle"] == DEFAULT_POOL_RECYCLE_SECONDS
    assert captured["pool_recycle"] == 300
    assert str(captured["url"]).startswith("postgresql+psycopg://")


def test_settings_pool_recycle_default_matches_neon_window() -> None:
    settings = Settings(_env_file=None)
    assert settings.database_pool_recycle == DEFAULT_POOL_RECYCLE_SECONDS


def test_get_db_reuses_one_engine_across_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[MagicMock] = []

    def fake_create_db_engine(settings: Settings | None = None) -> MagicMock:
        engine = MagicMock(name=f"engine-{len(created)}")
        created.append(engine)
        return engine

    def fake_session_factory(engine: MagicMock):
        def factory() -> MagicMock:
            session = MagicMock(name="session")
            session.bind = engine
            return session

        return factory

    settings = _settings_with_url()
    monkeypatch.setattr("marketdata.api.deps.create_db_engine", fake_create_db_engine)
    monkeypatch.setattr("marketdata.api.deps.create_session_factory", fake_session_factory)
    monkeypatch.setattr("marketdata.api.deps.get_settings", lambda: settings)
    monkeypatch.setattr("marketdata.api.main.get_settings", lambda: settings)

    app = create_app()
    request = _request_for(app)
    first = _consume_session(request)
    second = _consume_session(request)

    assert len(created) == 1
    assert first.bind is created[0]
    assert second.bind is created[0]
    assert app.state.db_engine is created[0]


def test_api_does_not_call_create_db_engine_per_request(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[MagicMock] = []

    def fake_create_db_engine(settings: Settings | None = None) -> MagicMock:
        engine = MagicMock(name=f"engine-{len(created)}")
        created.append(engine)
        return engine

    def fake_session_factory(engine: MagicMock):
        def factory() -> MagicMock:
            session = MagicMock(name="session")
            session.bind = engine
            session.scalars.return_value.all.return_value = []
            return session

        return factory

    settings = _settings_with_url()
    monkeypatch.setattr("marketdata.api.deps.create_db_engine", fake_create_db_engine)
    monkeypatch.setattr("marketdata.api.deps.create_session_factory", fake_session_factory)
    monkeypatch.setattr("marketdata.api.deps.get_settings", lambda: settings)
    monkeypatch.setattr("marketdata.api.main.get_settings", lambda: settings)

    app = create_app()
    assert len(created) == 1
    client = TestClient(app)
    first = client.get("/v1/sources")
    second = client.get("/v1/sources")
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(created) == 1


def test_lifespan_disposes_engine_on_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[MagicMock] = []

    def fake_create_db_engine(settings: Settings | None = None) -> MagicMock:
        engine = MagicMock(name=f"engine-{uuid4().hex[:8]}")
        created.append(engine)
        return engine

    def fake_session_factory(engine: MagicMock):
        return lambda: MagicMock(bind=engine)

    settings = _settings_with_url()
    monkeypatch.setattr("marketdata.api.deps.create_db_engine", fake_create_db_engine)
    monkeypatch.setattr("marketdata.api.deps.create_session_factory", fake_session_factory)
    monkeypatch.setattr("marketdata.api.deps.get_settings", lambda: settings)
    monkeypatch.setattr("marketdata.api.main.get_settings", lambda: settings)

    app = create_app()
    assert len(created) == 1
    engine = created[0]
    with TestClient(app) as client:
        client.get("/v1/health")
        # Idempotent bind during lifespan startup must not create a second engine.
        assert len(created) == 1
        assert app.state.db_engine is engine
    engine.dispose.assert_called_once()
    assert app.state.db_engine is None
    assert app.state.session_factory is None


def test_bind_database_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[MagicMock] = []

    def fake_create_db_engine(settings: Settings | None = None) -> MagicMock:
        engine = MagicMock()
        created.append(engine)
        return engine

    monkeypatch.setattr("marketdata.api.deps.create_db_engine", fake_create_db_engine)
    monkeypatch.setattr(
        "marketdata.api.deps.create_session_factory",
        lambda engine: MagicMock(name="factory"),
    )
    app = FastAPI()
    settings = _settings_with_url()
    bind_database(app, settings)
    bind_database(app, settings)
    assert len(created) == 1
    dispose_database(app)
    created[0].dispose.assert_called_once()
