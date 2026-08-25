from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from marketdata.datasets.schema import SCHEMA_VERSION

CATALOG_NAMES: tuple[str, ...] = ("sources", "instruments", "quotes", "fund_nav", "rates")
BLOCKED_MANIFEST_SOURCES = frozenset({"b3", "yahoo"})


def parquet_object_key(name: str, snapshot_date: date) -> str:
    return f"public/datasets/{name}/schema_v1/{snapshot_date.isoformat()}.parquet"


def versioned_manifest_key(name: str, snapshot_date: date) -> str:
    return f"public/manifests/{name}/{snapshot_date.isoformat()}.json"


def latest_manifest_key(name: str) -> str:
    return f"public/manifests/{name}-latest.json"


class ReferencePeriod(BaseModel):
    start: date | None = None
    end: date | None = None


class DatasetManifest(BaseModel):
    model_config = ConfigDict(ser_json_bytes="base64")

    dataset_name: str
    schema_version: str = SCHEMA_VERSION
    snapshot_date: date
    generated_at: datetime
    sources: list[str]
    reference_period: ReferencePeriod
    row_count: int
    object_key: str
    sha256: str
    license: Literal["ODbL-1.0"] = "ODbL-1.0"
    redistribution_policy: Literal["PUBLIC_WITH_ATTRIBUTION"] = "PUBLIC_WITH_ATTRIBUTION"
    attribution: list[str] = Field(default_factory=list)
    url: str | None = None


def is_allowlisted_name(name: str) -> bool:
    return name in CATALOG_NAMES


def manifest_contains_blocked_source(sources: list[str]) -> bool:
    return any(source in BLOCKED_MANIFEST_SOURCES for source in sources)
