import json
from datetime import date

from sqlalchemy.orm import Session

from marketdata.domain.enums import IngestionRunStatus, RedistributionPolicy
from marketdata.providers.bcb import SGS_SERIES, BcbProvider
from marketdata.storage.object_store import LocalFileObjectStorage, build_object_storage
from marketdata.storage.repositories import (
    finish_ingestion_run,
    get_or_create_market_series,
    get_or_create_source,
    start_ingestion_run,
    store_raw_artifact,
    upsert_series_observation,
)


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
    source = get_or_create_source(
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
            source_url="https://api.bcb.gov.br/dados/serie/bcdata.sgs",
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
