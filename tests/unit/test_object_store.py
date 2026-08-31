import pytest

from marketdata.config import Settings
from marketdata.storage.object_store import (
    LocalFileObjectStorage,
    ObjectStorageError,
    public_publication_storage_configured,
)


def test_local_object_storage_round_trip(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    uri = store.store("raw/cvm/sample.zip", b"hello")
    assert store.exists("raw/cvm/sample.zip")
    assert store.retrieve("raw/cvm/sample.zip") == b"hello"
    assert uri.startswith("file:")


def test_local_object_storage_missing_key(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    with pytest.raises(ObjectStorageError):
        store.retrieve("missing.bin")


def test_local_object_storage_rejects_parent_escape(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    with pytest.raises(ObjectStorageError):
        store.store("../secret", b"nope")


def test_local_object_storage_replace_overwrites(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    store.store("public/manifests/quotes-latest.json", b"v1")
    store.store("public/manifests/quotes-latest.json", b"v2-complete")
    assert store.retrieve("public/manifests/quotes-latest.json") == b"v2-complete"
    leftovers = list(tmp_path.rglob(".tmp-*"))
    assert leftovers == []


def test_public_publication_storage_configured_requires_s3_backend() -> None:
    local = Settings(_env_file=None, object_storage_backend="local")
    unset = Settings(_env_file=None, object_storage_backend="")
    s3 = Settings(_env_file=None, object_storage_backend="s3", object_storage_bucket="datasets")
    assert public_publication_storage_configured(local) is False
    assert public_publication_storage_configured(unset) is False
    assert public_publication_storage_configured(s3) is True
