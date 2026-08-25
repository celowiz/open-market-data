from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from logging import getLogger
from typing import Literal

import polars as pl
from sqlalchemy.orm import Session

from marketdata.datasets.attribution import attribution_for
from marketdata.datasets.extract import EXTRACTORS
from marketdata.datasets.manifest import (
    CATALOG_NAMES,
    DatasetManifest,
    ReferencePeriod,
    latest_manifest_key,
    parquet_object_key,
    versioned_manifest_key,
)
from marketdata.datasets.parquet import assert_value_not_float, sha256_hex, write_parquet_bytes
from marketdata.datasets.schema import CATALOG_SCHEMAS, validate_frame
from marketdata.storage.object_store import ObjectStorage

logger = getLogger(__name__)

Extractor = Callable[[Session | None], pl.DataFrame]
PublishStatus = Literal["published", "skipped", "failed", "dry_run"]


class DatasetPublishError(RuntimeError):
    """Raised when a dataset cannot be published atomically."""


@dataclass
class DatasetOutcome:
    name: str
    status: PublishStatus
    row_count: int = 0
    object_key: str | None = None
    sha256: str | None = None
    error: str | None = None


@dataclass
class PublishSummary:
    snapshot_date: date
    dry_run: bool
    outcomes: list[DatasetOutcome] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(outcome.status == "failed" for outcome in self.outcomes)


def _reference_period(frame: pl.DataFrame) -> ReferencePeriod:
    if "reference_date" not in frame.columns or frame.height == 0:
        return ReferencePeriod()
    start = frame["reference_date"].min()
    end = frame["reference_date"].max()
    return ReferencePeriod(
        start=start if isinstance(start, date) else None,
        end=end if isinstance(end, date) else None,
    )


def _sources_in_frame(name: str, frame: pl.DataFrame) -> list[str]:
    if "source" in frame.columns:
        return sorted({value for value in frame["source"].to_list() if value is not None})
    if name == "sources" and "name" in frame.columns:
        return sorted({value for value in frame["name"].to_list() if value is not None})
    return []


def _public_url(object_key: str, public_data_base_url: str) -> str | None:
    base = public_data_base_url.strip()
    if not base:
        return None
    return f"{base.rstrip('/')}/{object_key}"


def _build_manifest(
    *,
    name: str,
    snapshot_date: date,
    frame: pl.DataFrame,
    object_key: str,
    digest: str,
    generated_at: datetime,
    public_data_base_url: str,
) -> DatasetManifest:
    sources = _sources_in_frame(name, frame)
    return DatasetManifest(
        dataset_name=name,
        snapshot_date=snapshot_date,
        generated_at=generated_at,
        sources=sources,
        reference_period=_reference_period(frame),
        row_count=frame.height,
        object_key=object_key,
        sha256=digest,
        attribution=attribution_for(sources),
        url=_public_url(object_key, public_data_base_url),
    )


def _publish_one(
    *,
    name: str,
    frame: pl.DataFrame,
    store: ObjectStorage,
    snapshot_date: date,
    dry_run: bool,
    generated_at: datetime,
    public_data_base_url: str,
) -> DatasetOutcome:
    if frame.height == 0:
        logger.info("skipping empty dataset %s", name)
        return DatasetOutcome(name=name, status="skipped", row_count=0)

    schema = CATALOG_SCHEMAS[name]
    validate_frame(frame, schema)
    if "value" in frame.columns:
        assert_value_not_float(frame)

    payload = write_parquet_bytes(frame)
    digest = sha256_hex(payload)
    object_key = parquet_object_key(name, snapshot_date)
    if dry_run:
        return DatasetOutcome(
            name=name,
            status="dry_run",
            row_count=frame.height,
            object_key=object_key,
            sha256=digest,
        )

    store.store(object_key, payload, content_type="application/vnd.apache.parquet")
    stored = store.retrieve(object_key)
    stored_digest = sha256_hex(stored)
    if stored_digest != digest:
        raise DatasetPublishError(f"parquet checksum mismatch for {name}")

    manifest = _build_manifest(
        name=name,
        snapshot_date=snapshot_date,
        frame=frame,
        object_key=object_key,
        digest=digest,
        generated_at=generated_at,
        public_data_base_url=public_data_base_url,
    )
    encoded = manifest.model_dump_json().encode("utf-8")
    store.store(
        versioned_manifest_key(name, snapshot_date),
        encoded,
        content_type="application/json",
    )
    store.store(latest_manifest_key(name), encoded, content_type="application/json")
    return DatasetOutcome(
        name=name,
        status="published",
        row_count=frame.height,
        object_key=object_key,
        sha256=digest,
    )


def publish_datasets(
    *,
    store: ObjectStorage,
    snapshot_date: date,
    session: Session | None = None,
    names: Sequence[str] | None = None,
    dry_run: bool = False,
    public_data_base_url: str = "",
    extractors: dict[str, Extractor] | None = None,
    now: datetime | None = None,
) -> PublishSummary:
    requested = list(names) if names is not None else list(CATALOG_NAMES)
    unknown = [name for name in requested if name not in CATALOG_NAMES]
    if unknown:
        raise DatasetPublishError(f"unknown dataset names: {', '.join(unknown)}")

    generated_at = now or datetime.now(UTC)
    summary = PublishSummary(snapshot_date=snapshot_date, dry_run=dry_run)
    for name in requested:
        try:
            if extractors is None:
                if session is None:
                    raise DatasetPublishError("a database session is required to extract datasets")
                frame = EXTRACTORS[name](session)
            else:
                frame = extractors[name](session)
            outcome = _publish_one(
                name=name,
                frame=frame,
                store=store,
                snapshot_date=snapshot_date,
                dry_run=dry_run,
                generated_at=generated_at,
                public_data_base_url=public_data_base_url,
            )
        except Exception as exc:
            logger.exception("dataset %s failed", name)
            summary.outcomes.append(DatasetOutcome(name=name, status="failed", error=str(exc)))
            continue
        summary.outcomes.append(outcome)
    return summary
