from __future__ import annotations

from datetime import date
from logging import getLogger

import httpx
from sqlalchemy.orm import Session

from marketdata.domain.enums import IngestionRunStatus, RedistributionPolicy
from marketdata.providers.cvm_events import CvmEventsProvider, fato_relevante_url
from marketdata.storage.object_store import build_object_storage
from marketdata.storage.repositories import (
    finish_ingestion_run,
    get_or_create_cvm_source,
    resolve_instrument_id,
    start_ingestion_run,
    store_raw_artifact,
    upsert_event,
)

logger = getLogger(__name__)


def ingest_cvm_events(
    session: Session,
    *,
    reference_date: date,
    payload: bytes | None = None,
    provider: CvmEventsProvider | None = None,
) -> dict[str, int | str]:
    events = provider or CvmEventsProvider()
    object_store = build_object_storage()
    source = get_or_create_cvm_source(session)
    source.redistribution_policy = RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION.value
    run = start_ingestion_run(
        session, provider="cvm-events", source_id=source.id, reference_date=reference_date
    )
    inserted = skipped = 0
    url = fato_relevante_url(reference_date.year)
    try:
        try:
            records = events.fetch_year(reference_date.year, payload=payload)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            logger.info("CVM fatos relevantes skipped: HTTP %s for %s", status, url)
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
        except httpx.HTTPError as exc:
            logger.info("CVM fatos relevantes skipped: %s", type(exc).__name__)
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
        raw = payload if payload is not None else b""
        if payload is None:
            raw = "\n".join(
                f"{row.ticker};{row.external_id};{row.headline}" for row in records
            ).encode("utf-8")
        artifact = store_raw_artifact(
            session,
            source_id=source.id,
            ingestion_run_id=run.id,
            source_url=url,
            payload=raw or b"[]",
            storage_uri=object_store.store(
                f"raw/cvm/fatos/{reference_date.year}.csv",
                raw or b"[]",
                content_type="text/csv",
            ),
            filename=f"fato_relevante_cia_aberta_{reference_date.year}.csv",
            content_type="text/csv",
            http_status=200,
            etag=None,
            last_modified=None,
            reference_date=reference_date,
        )
        for row in records:
            action = upsert_event(
                session,
                ticker=row.ticker,
                instrument_id=resolve_instrument_id(session, row.ticker),
                source="cvm",
                event_type="fato_relevante",
                occurred_at=row.occurred_at,
                headline=row.headline,
                url=row.url,
                external_id=row.external_id,
                raw_artifact_id=artifact.id,
                ingestion_run_id=run.id,
            )
            if action == "inserted":
                inserted += 1
            else:
                skipped += 1
        run.artifacts_downloaded = 1
        run.records_inserted = inserted
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        return {
            "run_id": str(run.id),
            "inserted": inserted,
            "updated": 0,
            "skipped": skipped,
            "artifacts": 1,
            "status": run.status,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise
