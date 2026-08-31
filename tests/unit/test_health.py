from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from marketdata.api.main import create_app
from marketdata.config import Settings, get_settings


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_without_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    empty = Settings(_env_file=None, database_url="")
    monkeypatch.setattr("marketdata.api.routes.health.get_settings", lambda: empty)
    client = TestClient(create_app())
    response = client.get("/v1/health", params={"ready": 1})
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unready"
    assert "DATABASE_URL" in body["detail"]


def test_health_ready_returns_503_when_ping_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, database_url="postgresql://u:p@127.0.0.1:1/missing")
    monkeypatch.setattr("marketdata.api.routes.health.get_settings", lambda: settings)

    def boom(_engine: object) -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr("marketdata.api.routes.health.ping_database", boom)
    client = TestClient(create_app())
    response = client.get("/v1/health", params={"ready": "1"})
    assert response.status_code == 503
    assert response.json()["status"] == "unready"


def test_health_liveness_does_not_ping_database(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_ping(_engine: object) -> None:
        raise AssertionError("liveness must not ping Postgres")

    monkeypatch.setattr("marketdata.api.routes.health.ping_database", fail_ping)
    client = TestClient(create_app())
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_openapi_documents_ready_query() -> None:
    spec = TestClient(create_app()).get("/openapi.json").json()
    operation = spec["paths"]["/v1/health"]["get"]
    params = {item["name"]: item for item in operation.get("parameters", [])}
    assert "ready" in params
    assert params["ready"].get("required") is not True
    assert params["ready"]["schema"]["type"] == "boolean"
    assert params["ready"]["schema"]["default"] is False
    assert "503" in operation["responses"]


@pytest.mark.db
def test_health_ready_pings_postgres() -> None:
    settings = get_settings()
    if not settings.database_url:
        pytest.skip("DATABASE_URL is not configured")
    client = TestClient(create_app())
    response = client.get("/v1/health", params={"ready": 1})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_pings_bound_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, database_url="postgresql://u:p@localhost/db")
    monkeypatch.setattr("marketdata.api.routes.health.get_settings", lambda: settings)
    engine = MagicMock(name="engine")
    pinged: list[object] = []

    def fake_ping(bound: object) -> None:
        pinged.append(bound)

    monkeypatch.setattr("marketdata.api.routes.health.ping_database", fake_ping)
    app = create_app()
    app.state.db_engine = engine
    client = TestClient(app)
    response = client.get("/v1/health", params={"ready": 1})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert pinged == [engine]
