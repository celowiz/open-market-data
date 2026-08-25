"""S3ObjectStorage tests use an in-process stub client.

They do not require AWS credentials or `uv sync --extra s3`. That extra is only
needed when `OBJECT_STORAGE_BACKEND=s3` talks to a real S3-compatible endpoint.
"""

from __future__ import annotations

import importlib
import io
from pathlib import Path

import pytest

from marketdata.config import Settings
from marketdata.storage.object_store import (
    LocalFileObjectStorage,
    ObjectStorageError,
    build_object_storage,
)
from marketdata.storage.s3_store import S3ObjectStorage


class FakeNotFound(Exception):
    def __init__(self) -> None:
        super().__init__("not found")
        self.response = {
            "Error": {"Code": "404"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        }


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str | None] = {}
        self.calls: list[tuple[str, dict[str, object]]] = []

    def put_object(self, **kwargs: object) -> dict[str, str]:
        self.calls.append(("put_object", dict(kwargs)))
        key = str(kwargs["Key"])
        body = kwargs["Body"]
        if not isinstance(body, bytes):
            raise TypeError("Body must be bytes")
        self.objects[key] = body
        content_type = kwargs.get("ContentType")
        self.content_types[key] = str(content_type) if content_type is not None else None
        return {"ETag": '"stub"'}

    def get_object(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("get_object", dict(kwargs)))
        key = str(kwargs["Key"])
        if key not in self.objects:
            raise FakeNotFound()
        return {"Body": io.BytesIO(self.objects[key])}

    def head_object(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("head_object", dict(kwargs)))
        key = str(kwargs["Key"])
        if key not in self.objects:
            raise FakeNotFound()
        return {}


def _store(client: FakeS3Client | None = None) -> tuple[S3ObjectStorage, FakeS3Client]:
    stub = client or FakeS3Client()
    store = S3ObjectStorage(
        bucket="artifacts",
        endpoint_url="https://example.r2.cloudflarestorage.com",
        access_key="ak",
        secret_key="sk",
        region="auto",
        client=stub,
    )
    return store, stub


def _patch_settings(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> Settings:
    settings = Settings(_env_file=None, **overrides)
    monkeypatch.setattr("marketdata.config.get_settings", lambda: settings)
    return settings


def test_s3_store_round_trip_with_stub_client() -> None:
    store, _ = _store()
    uri = store.store("raw/cvm/sample.zip", b"hello", content_type="application/zip")

    assert uri == "s3://artifacts/raw/cvm/sample.zip"
    assert store.exists("raw/cvm/sample.zip") is True
    assert store.retrieve("raw/cvm/sample.zip") == b"hello"


def test_s3_store_overwrite_and_content_type() -> None:
    store, stub = _store()
    store.store("public/manifests/latest.json", b"v1", content_type="application/json")
    store.store("public/manifests/latest.json", b"v2", content_type="application/json")

    assert store.retrieve("public/manifests/latest.json") == b"v2"
    assert stub.content_types["public/manifests/latest.json"] == "application/json"
    put_calls = [kwargs for name, kwargs in stub.calls if name == "put_object"]
    assert all(kwargs["Bucket"] == "artifacts" for kwargs in put_calls)


def test_s3_store_missing_key() -> None:
    store, _ = _store()
    assert store.exists("missing.bin") is False
    with pytest.raises(ObjectStorageError, match="object not found"):
        store.retrieve("missing.bin")


def test_s3_store_rejects_parent_escape() -> None:
    store, stub = _store()
    with pytest.raises(ObjectStorageError, match="unsafe object key"):
        store.store("../secret", b"nope")
    with pytest.raises(ObjectStorageError, match="unsafe object key"):
        store.retrieve("state/backfill/../secret.json")
    with pytest.raises(ObjectStorageError, match="unsafe object key"):
        store.exists("state/backfill/../secret.json")
    assert stub.objects == {}
    assert stub.calls == []


def test_s3_store_requires_bucket() -> None:
    with pytest.raises(ObjectStorageError, match="bucket"):
        S3ObjectStorage(
            bucket="",
            endpoint_url="https://example.r2.cloudflarestorage.com",
            access_key="ak",
            secret_key="sk",
        )


def test_s3_client_uses_path_style_and_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeConfig:
        def __init__(self, **kwargs: object) -> None:
            self.options = kwargs

    class FakeBoto3:
        def client(self, service: str, **kwargs: object) -> FakeS3Client:
            captured["service"] = service
            captured["kwargs"] = kwargs
            return FakeS3Client()

    monkeypatch.setattr(
        "marketdata.storage.s3_store._import_boto3",
        lambda: (FakeBoto3(), FakeConfig),
    )
    store = S3ObjectStorage(
        bucket="artifacts",
        endpoint_url="https://example.r2.cloudflarestorage.com",
        access_key="ak",
        secret_key="sk",
        region="auto",
    )
    store.store("raw/x.bin", b"ok")

    assert captured["service"] == "s3"
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["endpoint_url"] == "https://example.r2.cloudflarestorage.com"
    assert kwargs["aws_access_key_id"] == "ak"
    assert kwargs["aws_secret_access_key"] == "sk"
    assert kwargs["region_name"] == "auto"
    config = kwargs["config"]
    assert isinstance(config, FakeConfig)
    assert config.options == {"s3": {"addressing_style": "path"}}


def test_s3_client_is_lazy_until_first_operation() -> None:
    store = S3ObjectStorage(
        bucket="artifacts",
        endpoint_url="https://example.r2.cloudflarestorage.com",
        access_key="ak",
        secret_key="sk",
        client=None,
    )
    assert store._client is None


def test_missing_boto3_raises_install_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None) -> object:
        if name in {"boto3", "botocore.config"}:
            raise ImportError("simulated missing extra")
        return real_import(name, package)

    monkeypatch.setattr("marketdata.storage.s3_store.importlib.import_module", fake_import)
    store = S3ObjectStorage(
        bucket="artifacts",
        endpoint_url="https://example.r2.cloudflarestorage.com",
        access_key="ak",
        secret_key="sk",
    )
    with pytest.raises(ObjectStorageError, match="uv sync --extra s3"):
        store.exists("raw/x.bin")


def test_build_object_storage_local_ignores_missing_aws_creds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    _patch_settings(
        monkeypatch,
        object_storage_backend="local",
        local_storage_path=tmp_path,
        object_storage_access_key="",
        object_storage_secret_key="",
        object_storage_endpoint="",
        object_storage_bucket="",
    )
    store = build_object_storage()
    assert isinstance(store, LocalFileObjectStorage)
    store.store("raw/x.bin", b"ok")
    assert store.retrieve("raw/x.bin") == b"ok"


def test_build_object_storage_s3_does_not_import_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        object_storage_backend="s3",
        object_storage_endpoint="https://example.r2.cloudflarestorage.com",
        object_storage_bucket="artifacts",
        object_storage_access_key="ak",
        object_storage_secret_key="sk",
        object_storage_region="auto",
    )
    store = build_object_storage()
    assert isinstance(store, S3ObjectStorage)
    assert store._client is None


def test_build_object_storage_unknown_backend_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, object_storage_backend="minio")
    with pytest.raises(ValueError, match="unknown object storage backend"):
        build_object_storage()


def test_domain_ingestion_and_api_do_not_import_boto3() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "marketdata"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "s3_store.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "import boto3" in text or "from boto3" in text:
            offenders.append(str(path.relative_to(root.parent)))
    assert offenders == []


def test_s3_store_module_does_not_import_boto3_at_load() -> None:
    module = importlib.import_module("marketdata.storage.s3_store")
    imported = getattr(module, "__dict__", {})
    assert "boto3" not in imported
    source = Path(module.__file__ or "").read_text(encoding="utf-8")
    tree_imports = [
        line.strip()
        for line in source.splitlines()
        if line.startswith("import boto3") or line.startswith("from boto3")
    ]
    assert tree_imports == []


def test_build_object_storage_accepts_s3_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        object_storage_backend="S3",
        object_storage_bucket="artifacts",
        object_storage_endpoint="https://example.r2.cloudflarestorage.com",
        object_storage_access_key="ak",
        object_storage_secret_key="sk",
    )
    store = build_object_storage()
    assert isinstance(store, S3ObjectStorage)
