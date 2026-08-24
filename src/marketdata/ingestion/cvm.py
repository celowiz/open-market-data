from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from marketdata.config import get_settings
from marketdata.domain.enums import IngestionRunStatus
from marketdata.providers.cvm import (
    CvmParseError,
    CvmProvider,
    extract_csv_from_zip,
    months_covering,
    parse_informe_diario,
)
from marketdata.storage.object_store import LocalFileObjectStorage, build_object_storage
from marketdata.storage.repositories import (
    finish_ingestion_run,
    get_or_create_cvm_source,
    get_or_create_fund_instrument,
    start_ingestion_run,
    store_raw_artifact,
    upsert_fund_nav_quote,
)


def ingest_cvm(
    session: Session,
    *,
    reference_date: date,
    lookback_days: int | None = None,
    storage: LocalFileObjectStorage | None = None,
    provider: CvmProvider | None = None,
) -> dict[str, int | str]:
    settings = get_settings()
    days = settings.recent_reprocess_days if lookback_days is None else lookback_days
    cvm = provider or CvmProvider()
    object_store = storage or build_object_storage()
    source = get_or_create_cvm_source(session)
    run = start_ingestion_run(
        session, provider=cvm.name, source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = rejected = 0
    artifacts = 0
    try:
        for year, month in months_covering(reference_date, days):
            response = cvm.fetch_month(year, month)
            payload = response.content
            key = (
                f"raw/cvm/year={year:04d}/month={month:02d}/inf_diario_fi_{year:04d}{month:02d}.zip"
            )
            uri = object_store.store(key, payload, content_type="application/zip")
            artifact = store_raw_artifact(
                session,
                source_id=source.id,
                ingestion_run_id=run.id,
                source_url=str(response.request.url)
                if response.request is not None
                else cvm.month_url(year, month),
                payload=payload,
                storage_uri=uri,
                filename=f"inf_diario_fi_{year:04d}{month:02d}.zip",
                content_type=response.headers.get("content-type"),
                http_status=response.status_code,
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
                reference_date=date(year, month, 1),
            )
            artifacts += 1
            try:
                csv_text = extract_csv_from_zip(payload)
                records = parse_informe_diario(csv_text)
            except CvmParseError:
                rejected += 1
                continue
            run.records_parsed += len(records)
            for record in records:
                if record.quota_value <= 0:
                    rejected += 1
                    continue
                instrument = get_or_create_fund_instrument(
                    session, source_id=source.id, record=record
                )
                action = upsert_fund_nav_quote(
                    session,
                    instrument_id=instrument.id,
                    source_id=source.id,
                    record=record,
                    artifact=artifact,
                    ingestion_run_id=run.id,
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
        run.records_rejected = rejected
        run.records_normalized = inserted + updated + skipped
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        return {
            "run_id": str(run.id),
            "artifacts": artifacts,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "rejected": rejected,
            "status": run.status,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise
