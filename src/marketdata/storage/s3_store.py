from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from marketdata.storage.object_store import ObjectStorageError


def _import_boto3() -> tuple[Any, Any]:
    try:
        boto3 = importlib.import_module("boto3")
        config_mod = importlib.import_module("botocore.config")
    except ImportError as exc:
        raise ObjectStorageError(
            "S3 object storage requires boto3; install with: uv sync --extra s3"
        ) from exc
    return boto3, config_mod.Config


def _normalize_key(key: str) -> str:
    relative = Path(key.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ObjectStorageError(f"unsafe object key: {key}")
    return relative.as_posix()


def _is_not_found(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    error = response.get("Error")
    if isinstance(error, dict):
        code = str(error.get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return True
    metadata = response.get("ResponseMetadata")
    if isinstance(metadata, dict) and metadata.get("HTTPStatusCode") == 404:
        return True
    return False


def _read_body(body: Any) -> bytes:
    if body is None:
        raise ObjectStorageError("s3 get_object returned no body")
    if isinstance(body, bytes):
        return body
    read = getattr(body, "read", None)
    if not callable(read):
        raise ObjectStorageError("s3 get_object returned an unreadable body")
    payload = read()
    close = getattr(body, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, bytearray | memoryview):
        return bytes(payload)
    raise ObjectStorageError("s3 get_object returned an unreadable body")


class S3ObjectStorage:
    """S3-compatible object storage (Cloudflare R2 via path-style addressing)."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str = "",
        access_key: str = "",
        secret_key: str = "",
        region: str = "auto",
        client: Any | None = None,
    ) -> None:
        if not bucket:
            raise ObjectStorageError("object storage bucket is required for the s3 backend")
        self._bucket = bucket
        self._endpoint_url = endpoint_url
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region or "auto"
        self._client = client

    def store(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        object_key = _normalize_key(key)
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": object_key,
            "Body": data,
        }
        if content_type:
            kwargs["ContentType"] = content_type
        try:
            self._get_client().put_object(**kwargs)
        except ObjectStorageError:
            raise
        except Exception as exc:
            raise ObjectStorageError(f"s3 store failed for {key}: {exc}") from exc
        return f"s3://{self._bucket}/{object_key}"

    def retrieve(self, key: str) -> bytes:
        object_key = _normalize_key(key)
        try:
            response = self._get_client().get_object(Bucket=self._bucket, Key=object_key)
            return _read_body(response.get("Body"))
        except ObjectStorageError:
            raise
        except Exception as exc:
            if _is_not_found(exc):
                raise ObjectStorageError(f"object not found: {key}") from exc
            raise ObjectStorageError(f"s3 retrieve failed for {key}: {exc}") from exc

    def exists(self, key: str) -> bool:
        object_key = _normalize_key(key)
        try:
            self._get_client().head_object(Bucket=self._bucket, Key=object_key)
        except ObjectStorageError:
            raise
        except Exception as exc:
            if _is_not_found(exc):
                return False
            raise ObjectStorageError(f"s3 exists failed for {key}: {exc}") from exc
        return True

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self) -> Any:
        boto3, config_cls = _import_boto3()
        kwargs: dict[str, Any] = {
            "region_name": self._region,
            "config": config_cls(s3={"addressing_style": "path"}),
        }
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        if self._access_key and self._secret_key:
            kwargs["aws_access_key_id"] = self._access_key
            kwargs["aws_secret_access_key"] = self._secret_key
        return boto3.client("s3", **kwargs)
