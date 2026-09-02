from __future__ import annotations

from datetime import date
from logging import getLogger

from sqlalchemy.orm import Session

from marketdata.domain.enums import IngestionRunStatus, RedistributionPolicy
from marketdata.providers.ibge import IBGE_SERIES, IbgeProvider
from marketdata.storage.object_store import build_object_storage
from marketdata.storage.repositories import (
    finish_ingestion_run,
    get_or_create_market_series,
    get_or_create_source,
    start_ingestion_run,
    store_raw_artifact,
    upsert_series_observation,
)

logger = getLogger(__name__)


def ingest_ibge(
    session: Session,
    *,
    reference_date: date,
    observations: list | None = None,
    provider: IbgeProvider | None = None,
) -> dict[str, int | str]:
    ibge = provider or IbgeProvider()
    object_store = build_object_storage()
    source = get_or_create_source(
        session,
        name="ibge",
        display_name="IBGE SIDRA",
        official=True,
        homepage="https://sidra.ibge.gov.br/",
        documentation_url="https://apisidra.ibge.gov.br/home/ajuda",
        data_license="CC-BY",
        redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )
    run = start_ingestion_run(
        session, provider=ibge.name, source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = artifacts = 0
    period = f"{reference_date.year:04d}{reference_date.month:02d}"
    try:
        fetched = observations
        if fetched is None:
            fetched = []
            for code, table, variable, name, unit, template in IBGE_SERIES:
                try:
                    rows = ibge.fetch_series(
                        code=code,
                        table=table,
                        variable=variable,
                        name=name,
                        unit=unit,
                        path_template=template,
                        period=period,
                    )
                except Exception as exc:
                    logger.info("ibge skip series=%s error=%s", code, type(exc).__name__)
                    skipped += 1
                    continue
                if not rows:
                    skipped += 1
                    continue
                fetched.extend(rows)
        import json

        payload = json.dumps(
            [
                {
                    "code": row.code,
                    "date": row.reference_date.isoformat(),
                    "value": str(row.value),
                }
                for row in fetched
            ]
        ).encode("utf-8")
        artifact = store_raw_artifact(
            session,
            source_id=source.id,
            ingestion_run_id=run.id,
            source_url="https://apisidra.ibge.gov.br/values",
            payload=payload,
            storage_uri=object_store.store(
                f"raw/ibge/{reference_date.isoformat()}.json",
                payload,
                content_type="application/json",
            ),
            filename=f"ibge-{reference_date.isoformat()}.json",
            content_type="application/json",
            http_status=200,
            etag=None,
            last_modified=None,
            reference_date=reference_date,
        )
        artifacts += 1
        for row in fetched:
            series = get_or_create_market_series(
                session,
                source_id=source.id,
                code=row.code,
                source_series_id=row.source_series_id,
                name=row.name,
                unit=row.unit,
            )
            action = upsert_series_observation(
                session,
                series_id=series.id,
                source_id=source.id,
                reference_date=row.reference_date,
                value=row.value,
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
