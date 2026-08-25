from json import JSONDecodeError, loads

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from marketdata.api.deps import get_object_storage
from marketdata.config import get_settings
from marketdata.datasets.manifest import (
    CATALOG_NAMES,
    DatasetManifest,
    is_allowlisted_name,
    latest_manifest_key,
    manifest_contains_blocked_source,
)
from marketdata.storage.object_store import ObjectStorage, ObjectStorageError

router = APIRouter()


class DatasetListing(BaseModel):
    dataset_name: str
    schema_version: str
    snapshot_date: str
    generated_at: str
    sources: list[str]
    reference_period: dict[str, str | None]
    row_count: int
    object_key: str
    sha256: str
    license: str
    redistribution_policy: str
    attribution: list[str]
    url: str | None = None


def _public_url(object_key: str) -> str | None:
    base = get_settings().public_data_base_url.strip()
    if not base:
        return None
    return f"{base.rstrip('/')}/{object_key}"


def _load_latest(store: ObjectStorage, name: str) -> DatasetListing | None:
    if not is_allowlisted_name(name):
        return None
    key = latest_manifest_key(name)
    try:
        raw = store.retrieve(key)
    except ObjectStorageError:
        return None
    try:
        payload = loads(raw.decode("utf-8"))
        manifest = DatasetManifest.model_validate(payload)
    except (UnicodeDecodeError, JSONDecodeError, ValidationError, TypeError, ValueError):
        return None
    if manifest_contains_blocked_source(manifest.sources):
        return None
    dumped = manifest.model_dump(mode="json")
    dumped["url"] = _public_url(manifest.object_key)
    return DatasetListing.model_validate(dumped)


@router.get("/datasets", response_model=list[DatasetListing])
def list_datasets(store: ObjectStorage = Depends(get_object_storage)) -> list[DatasetListing]:
    listings: list[DatasetListing] = []
    for name in CATALOG_NAMES:
        listing = _load_latest(store, name)
        if listing is not None:
            listings.append(listing)
    return listings


@router.get("/datasets/{name}", response_model=DatasetListing)
def get_dataset(name: str, store: ObjectStorage = Depends(get_object_storage)) -> DatasetListing:
    if not is_allowlisted_name(name):
        raise HTTPException(status_code=404, detail="dataset not found")
    listing = _load_latest(store, name)
    if listing is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return listing
