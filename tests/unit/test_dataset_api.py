from datetime import UTC, datetime
from json import dumps

from fastapi.testclient import TestClient

from marketdata.api.deps import get_object_storage
from marketdata.api.main import create_app
from marketdata.datasets.manifest import latest_manifest_key
from marketdata.storage.object_store import LocalFileObjectStorage


def _manifest(
    *,
    name: str = "quotes",
    sources: list[str] | None = None,
    object_key: str = "public/datasets/quotes/schema_v1/2026-08-21.parquet",
) -> bytes:
    payload = {
        "dataset_name": name,
        "schema_version": "1",
        "snapshot_date": "2026-08-21",
        "generated_at": datetime(2026, 8, 21, 12, 0, tzinfo=UTC).isoformat(),
        "sources": sources if sources is not None else ["cvm", "tesouro"],
        "reference_period": {"start": "2026-08-03", "end": "2026-08-21"},
        "row_count": 2,
        "object_key": object_key,
        "sha256": "abc123",
        "license": "ODbL-1.0",
        "redistribution_policy": "PUBLIC_WITH_ATTRIBUTION",
        "attribution": ["data from Portal de Dados Abertos CVM, https://dados.cvm.gov.br/"],
        "url": None,
    }
    return dumps(payload).encode("utf-8")


def _client(store: LocalFileObjectStorage) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_object_storage] = lambda: store
    return TestClient(app)


def test_list_datasets_returns_allowlisted_latest_manifests(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    store.store(latest_manifest_key("quotes"), _manifest())
    store.store(latest_manifest_key("b3"), _manifest(name="b3", sources=["b3"]))
    client = _client(store)
    response = client.get("/v1/datasets")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["dataset_name"] == "quotes"
    assert body[0]["object_key"] == "public/datasets/quotes/schema_v1/2026-08-21.parquet"
    assert body[0]["sha256"] == "abc123"
    assert body[0]["row_count"] == 2
    assert body[0]["license"] == "ODbL-1.0"
    assert "PAR1" not in response.text


def test_get_dataset_by_name(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    store.store(latest_manifest_key("quotes"), _manifest())
    client = _client(store)
    response = client.get("/v1/datasets/quotes")
    assert response.status_code == 200
    assert response.json()["dataset_name"] == "quotes"
    assert response.headers["content-type"].startswith("application/json")


def test_get_dataset_rejects_path_traversal(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    store.store("raw/secret.bin", b"nope")
    client = _client(store)
    assert client.get("/v1/datasets/../raw").status_code == 404
    assert client.get("/v1/datasets/..%2Fraw").status_code == 404
    assert client.get("/v1/raw").status_code == 404


def test_unknown_or_missing_dataset_is_404(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    client = _client(store)
    assert client.get("/v1/datasets").json() == []
    assert client.get("/v1/datasets/quotes").status_code == 404
    assert client.get("/v1/datasets/not-a-catalog").status_code == 404


def test_manifest_with_blocked_source_is_hidden(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    store.store(latest_manifest_key("quotes"), _manifest(sources=["b3"]))
    store.store(latest_manifest_key("rates"), _manifest(name="rates", sources=["yahoo"]))
    client = _client(store)
    assert client.get("/v1/datasets").json() == []
    assert client.get("/v1/datasets/quotes").status_code == 404
    assert client.get("/v1/datasets/rates").status_code == 404


def test_dataset_url_only_when_public_data_base_url_set(tmp_path, monkeypatch) -> None:
    store = LocalFileObjectStorage(tmp_path)
    store.store(latest_manifest_key("quotes"), _manifest())
    client = _client(store)
    assert client.get("/v1/datasets/quotes").json()["url"] is None

    from marketdata.config import Settings

    monkeypatch.setattr(
        "marketdata.api.routes.datasets.get_settings",
        lambda: Settings(_env_file=None, public_data_base_url="https://data.example.com"),
    )
    body = client.get("/v1/datasets/quotes").json()
    assert body["url"] == (
        "https://data.example.com/public/datasets/quotes/schema_v1/2026-08-21.parquet"
    )
