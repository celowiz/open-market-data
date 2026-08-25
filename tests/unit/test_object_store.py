import pytest

from marketdata.storage.object_store import LocalFileObjectStorage, ObjectStorageError


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
