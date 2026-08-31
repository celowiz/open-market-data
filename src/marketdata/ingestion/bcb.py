import json
from datetime import date

from sqlalchemy.orm import Session

from marketdata.domain.enums import IngestionRunStatus, RedistributionPolicy
from marketdata.ingestion.checkpoint import (
    BackfillCheckpoint,
    effective_last_completed,
    load_checkpoint,
    save_checkpoint,
)
from marketdata.providers.bcb import SGS_SERIES, BcbProvider, chunk_date_range
from marketdata.storage.object_store import LocalFileObjectStorage, build_object_storage
from marketdata.storage.repositories import (
    finish_ingestion_run,
    get_or_create_market_series,
    get_or_create_source,
    max_observation_reference_date,
    start_ingestion_run,
    store_raw_artifact,
    upsert_series_observation,
)

_BACKFILL_FLUSH_EVERY = 1000
_SGS_SOURCE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"


def _ensure_bcb_source(session: Session):
    return get_or_create_source(
        session,
        name="bcb",
        display_name="Banco Central do Brasil",
        official=True,
        homepage="https://dadosabertos.bcb.gov.br",
        documentation_url="https://api.bcb.gov.br/",
        data_license="ODbL-1.0",
        redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )


def _backfill_raw_key(code: str, chunk_start: date, chunk_end: date) -> str:
    # Local Windows storage rejects ':' in path segments (BCB:CDI_DAILY).
    safe_code = code.replace(":", "_")
    return f"raw/bcb/backfill/{safe_code}/{chunk_start.isoformat()}_{chunk_end.isoformat()}.json"


def ingest_bcb(
    session: Session,
    *,
    reference_date: date,
    storage: LocalFileObjectStorage | None = None,
    provider: BcbProvider | None = None,
    observations: list | None = None,
) -> dict[str, int | str]:
    bcb = provider or BcbProvider()
    object_store = storage or build_object_storage()
    source = _ensure_bcb_source(session)
    run = start_ingestion_run(
        session, provider=bcb.name, source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = 0
    payload_rows: list[dict[str, str]] = []
    try:
        fetched: list[tuple[str, str, str, str, date, object]] = []
        if observations is None:
            for code, series_id, name, unit in SGS_SERIES:
                for ref, value in bcb.fetch_series(
                    series_id, start=reference_date, end=reference_date
                ):
                    fetched.append((code, series_id, name, unit, ref, value))
                    payload_rows.append(
                        {"code": code, "date": ref.isoformat(), "value": str(value)}
                    )
        else:
            fetched = observations
            payload_rows = [
                {
                    "code": row[0],
                    "date": row[4].isoformat(),
                    "value": str(row[5]),
                }
                for row in fetched
            ]
        payload = json.dumps(payload_rows, indent=None).encode("utf-8")
        stamp = reference_date.isoformat()
        key = (
            f"raw/bcb/year={reference_date.year:04d}/"
            f"month={reference_date.month:02d}/sgs-{stamp}.json"
        )
        uri = object_store.store(key, payload, content_type="application/json")
        artifact = store_raw_artifact(
            session,
            source_id=source.id,
            ingestion_run_id=run.id,
            source_url=_SGS_SOURCE_URL,
            payload=payload,
            storage_uri=uri,
            filename=f"sgs-{reference_date.isoformat()}.json",
            content_type="application/json",
            http_status=200,
            etag=None,
            last_modified=None,
            reference_date=reference_date,
        )
        for code, series_id, name, unit, ref, value in fetched:
            series = get_or_create_market_series(
                session,
                source_id=source.id,
                code=code,
                source_series_id=series_id,
                name=name,
                unit=unit,
            )
            action = upsert_series_observation(
                session,
                series_id=series.id,
                source_id=source.id,
                reference_date=ref,
                value=value,
                artifact=artifact,
                ingestion_run_id=run.id,
                extra={"unit": unit},
            )
            if action == "inserted":
                inserted += 1
            elif action == "updated":
                updated += 1
            else:
                skipped += 1
        run.artifacts_downloaded = 1
        run.records_parsed = len(fetched)
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_normalized = inserted + updated + skipped
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        return {
            "run_id": str(run.id),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "status": run.status,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise


def _save_bcb_checkpoint(
    store,
    *,
    start: date,
    end: date,
    last_completed: date | None,
    status: str,
) -> None:
    save_checkpoint(
        store,
        BackfillCheckpoint(
            provider="bcb",
            start=start.isoformat(),
            end=end.isoformat(),
            last_completed=last_completed.isoformat() if last_completed else None,
            status=status,
        ),
    )


def _chunk_observations(
    observations: list | None,
    provider: BcbProvider,
    *,
    code: str,
    series_id: str,
    name: str,
    unit: str,
    chunk_start: date,
    chunk_end: date,
) -> list[tuple]:
    if observations is None:
        rows = provider.fetch_series(series_id, start=chunk_start, end=chunk_end)
        return [(code, series_id, name, unit, ref, value) for ref, value in rows]
    return [row for row in observations if row[0] == code and chunk_start <= row[4] <= chunk_end]


def backfill_bcb(
    session: Session,
    *,
    start: date,
    end: date,
    storage: LocalFileObjectStorage | None = None,
    provider: BcbProvider | None = None,
    observations: list | None = None,
    resume: bool = True,
) -> dict[str, int | str]:
    bcb = provider or BcbProvider()
    object_store = storage or build_object_storage()
    source = _ensure_bcb_source(session)
    run = start_ingestion_run(session, provider=bcb.name, source_id=source.id, reference_date=end)
    checkpoint = load_checkpoint(object_store, "bcb")
    db_last = None
    if resume:
        db_last = max_observation_reference_date(session, "bcb", start=start, end=end)
    token = effective_last_completed(checkpoint, start, end, db_last, resume=resume)
    completed_through = date.fromisoformat(token) if token else None
    _save_bcb_checkpoint(
        object_store,
        start=start,
        end=end,
        last_completed=completed_through,
        status="running",
    )
    inserted = updated = skipped = 0
    parsed = 0
    artifacts = 0
    pending_upserts = 0
    try:
        # Date windows outer, series inner: last_completed is an ISO date, so a
        # chunk is complete only after every SGS series for that window is stored.
        for chunk_start, chunk_end in chunk_date_range(start, end, years=10):
            if completed_through is not None and chunk_end <= completed_through:
                continue
            for code, series_id, name, unit in SGS_SERIES:
                fetched = _chunk_observations(
                    observations,
                    bcb,
                    code=code,
                    series_id=series_id,
                    name=name,
                    unit=unit,
                    chunk_start=chunk_start,
                    chunk_end=chunk_end,
                )
                payload_rows = [
                    {
                        "code": row[0],
                        "date": row[4].isoformat(),
                        "value": str(row[5]),
                    }
                    for row in fetched
                ]
                payload = json.dumps(payload_rows, indent=None).encode("utf-8")
                key = _backfill_raw_key(code, chunk_start, chunk_end)
                uri = object_store.store(key, payload, content_type="application/json")
                artifact = store_raw_artifact(
                    session,
                    source_id=source.id,
                    ingestion_run_id=run.id,
                    source_url=_SGS_SOURCE_URL,
                    payload=payload,
                    storage_uri=uri,
                    filename=f"{chunk_start.isoformat()}_{chunk_end.isoformat()}.json",
                    content_type="application/json",
                    http_status=200,
                    etag=None,
                    last_modified=None,
                    reference_date=chunk_end,
                )
                artifacts += 1
                parsed += len(fetched)
                series = get_or_create_market_series(
                    session,
                    source_id=source.id,
                    code=code,
                    source_series_id=series_id,
                    name=name,
                    unit=unit,
                )
                for _code, _series_id, _name, unit, ref, value in fetched:
                    action = upsert_series_observation(
                        session,
                        series_id=series.id,
                        source_id=source.id,
                        reference_date=ref,
                        value=value,
                        artifact=artifact,
                        ingestion_run_id=run.id,
                        extra={"unit": unit},
                    )
                    if action == "inserted":
                        inserted += 1
                    elif action == "updated":
                        updated += 1
                    else:
                        skipped += 1
                    pending_upserts += 1
                    if pending_upserts >= _BACKFILL_FLUSH_EVERY:
                        session.flush()
                        pending_upserts = 0
            completed_through = chunk_end
            session.commit()
            _save_bcb_checkpoint(
                object_store,
                start=start,
                end=end,
                last_completed=chunk_end,
                status="running",
            )
        run.artifacts_downloaded = artifacts
        run.records_parsed = parsed
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_normalized = inserted + updated + skipped
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.commit()
        _save_bcb_checkpoint(
            object_store,
            start=start,
            end=end,
            last_completed=end,
            status="succeeded",
        )
        return {
            "run_id": str(run.id),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "status": run.status,
        }
    except Exception:
        session.rollback()
        _save_bcb_checkpoint(
            object_store,
            start=start,
            end=end,
            last_completed=completed_through,
            status="failed",
        )
        raise
