import os
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable


class ObjectStorageError(Exception):
    """Raised when object storage cannot complete an operation."""


@runtime_checkable
class ObjectStorage(Protocol):
    def store(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        """Persist bytes and return a storage URI."""
        ...

    def retrieve(self, key: str) -> bytes:
        """Return previously stored bytes."""
        ...

    def exists(self, key: str) -> bool:
        """Return True if the key is present."""
        ...


class LocalFileObjectStorage:
    """Filesystem object storage used for local development and tests."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def store(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        del content_type
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".partial")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return path.as_uri()

    def retrieve(self, key: str) -> bytes:
        path = self._path_for(key)
        if not path.is_file():
            raise ObjectStorageError(f"object not found: {key}")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def _path_for(self, key: str) -> Path:
        relative = Path(key.replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ObjectStorageError(f"unsafe object key: {key}")
        return self._root / relative


def build_object_storage(root: Path | None = None) -> ObjectStorage:
    from marketdata.config import get_settings

    settings = get_settings()
    backend = (settings.object_storage_backend or "local").strip().lower()
    if backend == "local":
        base = root if root is not None else settings.local_storage_path
        return LocalFileObjectStorage(Path(base))
    if backend == "s3":
        from marketdata.storage.s3_store import S3ObjectStorage

        return S3ObjectStorage(
            bucket=settings.object_storage_bucket,
            endpoint_url=settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            region=settings.object_storage_region,
        )
    raise ValueError(f"unknown object storage backend: {backend!r}")
