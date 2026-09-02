from __future__ import annotations

from datetime import date
from logging import getLogger

from sqlalchemy.orm import Session

from marketdata.domain.enums import IngestionRunStatus, RedistributionPolicy
from marketdata.providers.cftc import CftcProvider
from marketdata.storage.object_store import build_object_storage
from marketdata.storage.repositories import (
    finish_ingestion_run,
    get_or_create_source,
    start_ingestion_run,
    store_raw_artifact,
    upsert_cot_snapshot,
)

logger = getLogger(__name__)


def ingest_cftc(
    session: Session,
    *,
    reference_date: date,
    records: list | None = None,
    provider: CftcProvider | None = None,
) -> dict[str, int | str]:
    cftc = provider or CftcProvider()
    object_store = build_object_storage()
    source = get_or_create_source(
        session,
        name="cftc",
        display_name="CFTC",
        official=True,
        homepage="https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
        documentation_url="https://publicreporting.cftc.gov/",
        data_license="PUBLIC",
        redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )
    run = start_ingestion_run(
        session, provider=cftc.name, source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = 0
    try:
        rows = records if records is not None else cftc.fetch_latest()
    except Exception as exc:
        logger.info("CFTC ingest skipped: %s", type(exc).__name__)
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        return {
            "run_id": str(run.id),
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "artifacts": 0,
            "status": "skipped",
        }
    try:
        import json

        payload = json.dumps(
            [
                {
                    "contract_code": row.contract_code,
                    "contract_name": row.contract_name,
                    "date": row.reference_date.isoformat(),
                    "open_interest": None if row.open_interest is None else str(row.open_interest),
                    "long_spec": None if row.long_spec is None else str(row.long_spec),
                    "short_spec": None if row.short_spec is None else str(row.short_spec),
                }
                for row in rows
            ]
        ).encode("utf-8")
        artifact = store_raw_artifact(
            session,
            source_id=source.id,
            ingestion_run_id=run.id,
            source_url="https://publicreporting.cftc.gov/",
            payload=payload,
            storage_uri=object_store.store(
                f"raw/cftc/{reference_date.isoformat()}.json",
                payload,
                content_type="application/json",
            ),
            filename=f"cftc-{reference_date.isoformat()}.json",
            content_type="application/json",
            http_status=200,
            etag=None,
            last_modified=None,
            reference_date=reference_date,
        )
        for row in rows:
            action = upsert_cot_snapshot(
                session,
                contract_code=row.contract_code,
                contract_name=row.contract_name,
                reference_date=row.reference_date,
                open_interest=row.open_interest,
                long_spec=row.long_spec,
                short_spec=row.short_spec,
                source_id=source.id,
                artifact=artifact,
                ingestion_run_id=run.id,
                extra=row.extra,
            )
            if action == "inserted":
                inserted += 1
            elif action == "updated":
                updated += 1
            else:
                skipped += 1
        run.artifacts_downloaded = 1
        run.records_inserted = inserted
        run.records_updated = updated
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        return {
            "run_id": str(run.id),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "artifacts": 1,
            "status": run.status,
        }
    except Exception as exc:
        logger.info("cftc ingest failed: %s", type(exc).__name__)
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise
