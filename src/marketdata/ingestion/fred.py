from __future__ import annotations

from datetime import date, timedelta
from logging import getLogger

from sqlalchemy.orm import Session

from marketdata.config import get_settings
from marketdata.domain.enums import (
    AssetClass,
    IdentifierType,
    IngestionRunStatus,
    PriceType,
    RedistributionPolicy,
)
from marketdata.ingestion.config_tables import load_fred_series
from marketdata.providers.fred import FredProvider
from marketdata.storage.object_store import build_object_storage
from marketdata.storage.repositories import (
    attach_identifier,
    finish_ingestion_run,
    get_or_create_instrument_by_key,
    get_or_create_source,
    start_ingestion_run,
    store_raw_artifact,
    upsert_quote,
)

logger = getLogger(__name__)
SKIPPED_NO_KEY = "skipped"


def ingest_fred(
    session: Session,
    *,
    reference_date: date,
    lookback_days: int = 7,
    observations: list | None = None,
    provider: FredProvider | None = None,
) -> dict[str, int | str]:
    settings = get_settings()
    if not settings.fred_api_key.strip() and observations is None:
        logger.info("FRED ingest skipped: FRED_API_KEY is not set.")
        return {
            "run_id": "",
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "artifacts": 0,
            "status": SKIPPED_NO_KEY,
        }
    fred = provider or FredProvider()
    object_store = build_object_storage()
    source = get_or_create_source(
        session,
        name="fred",
        display_name="FRED",
        official=True,
        homepage="https://fred.stlouisfed.org/",
        documentation_url="https://fred.stlouisfed.org/docs/api/fred/",
        data_license="PUBLIC",
        redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )
    run = start_ingestion_run(
        session, provider=fred.name, source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = artifacts = 0
    start = reference_date - timedelta(days=max(lookback_days, 0))
    specs = load_fred_series()
    try:
        for spec in specs:
            if observations is None:
                try:
                    rows = fred.fetch_observations(
                        spec.series_id,
                        api_key=settings.fred_api_key.strip(),
                        start=start,
                        end=reference_date,
                    )
                except Exception as exc:
                    logger.info("fred skip series=%s error=%s", spec.series_id, type(exc).__name__)
                    skipped += 1
                    continue
            else:
                rows = [
                    row
                    for row in observations
                    if getattr(row, "series_id", None) == spec.series_id
                ]
            if not rows:
                logger.info("fred skip empty series=%s date=%s", spec.series_id, reference_date)
                skipped += 1
                continue
            payload = _fred_payload(spec.series_id, rows)
            artifact = store_raw_artifact(
                session,
                source_id=source.id,
                ingestion_run_id=run.id,
                source_url=f"https://fred.stlouisfed.org/series/{spec.series_id}",
                payload=payload,
                storage_uri=object_store.store(
                    f"raw/fred/{spec.series_id}/{reference_date.isoformat()}.json",
                    payload,
                    content_type="application/json",
                ),
                filename=f"{spec.series_id}-{reference_date.isoformat()}.json",
                content_type="application/json",
                http_status=200,
                etag=None,
                last_modified=None,
                reference_date=reference_date,
            )
            artifacts += 1
            asset_class = _asset_class(spec.asset_class)
            instrument = get_or_create_instrument_by_key(
                session,
                source_id=source.id,
                source_key=spec.code,
                asset_class=asset_class,
                instrument_type=spec.asset_class,
                name=spec.name,
                currency=spec.currency,
            )
            attach_identifier(
                session,
                instrument_id=instrument.id,
                identifier_type=IdentifierType.TICKER,
                identifier_value=spec.series_id,
                source_id=source.id,
            )
            attach_identifier(
                session,
                instrument_id=instrument.id,
                identifier_type=IdentifierType.SOURCE_ID,
                identifier_value=spec.series_id,
                source_id=source.id,
            )
            for row in rows:
                action = upsert_quote(
                    session,
                    instrument_id=instrument.id,
                    source_id=source.id,
                    reference_date=row.reference_date,
                    value=row.value,
                    price_type=PriceType.REFERENCE,
                    artifact=artifact,
                    ingestion_run_id=run.id,
                    currency=spec.currency,
                    unit=spec.unit,
                    extra={"series_id": spec.series_id, "code": spec.code},
                    is_official=True,
                )
                if action == "inserted":
                    inserted += 1
                elif action == "updated":
                    updated += 1
                else:
                    skipped += 1
        run.artifacts_downloaded = artifacts
        run.records_inserted = inserted
        run.records_updated = updated
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        return {
            "run_id": str(run.id),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "artifacts": artifacts,
            "status": run.status,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise


def _fred_payload(series_id: str, rows) -> bytes:
    import json

    return json.dumps(
        {
            "series_id": series_id,
            "observations": [
                {"date": row.reference_date.isoformat(), "value": str(row.value)} for row in rows
            ],
        }
    ).encode("utf-8")


def _asset_class(raw: str) -> AssetClass:
    try:
        return AssetClass(raw)
    except ValueError:
        return AssetClass.OTHER
