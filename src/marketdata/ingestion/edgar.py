from __future__ import annotations

from datetime import date
from logging import getLogger

from sqlalchemy.orm import Session

from marketdata.domain.enums import IngestionRunStatus, RedistributionPolicy
from marketdata.providers.edgar import EdgarProvider
from marketdata.storage.object_store import build_object_storage
from marketdata.storage.repositories import (
    finish_ingestion_run,
    get_or_create_source,
    start_ingestion_run,
    store_raw_artifact,
    upsert_thirteen_f_holding,
)

logger = getLogger(__name__)


def ingest_13f(
    session: Session,
    *,
    reference_date: date,
    holdings: list | None = None,
    provider: EdgarProvider | None = None,
) -> dict[str, int | str]:
    edgar = provider or EdgarProvider()
    object_store = build_object_storage()
    source = get_or_create_source(
        session,
        name="edgar",
        display_name="SEC EDGAR 13F",
        official=True,
        homepage="https://www.sec.gov/edgar",
        documentation_url="https://www.sec.gov/edgar/searchedgar/companysearch",
        data_license="PUBLIC",
        redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        public_api_enabled=True,
        public_dataset_enabled=False,
    )
    run = start_ingestion_run(
        session, provider=edgar.name, source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = 0
    try:
        rows = holdings if holdings is not None else edgar.fetch_latest_holdings()
    except Exception as exc:
        logger.info("13F ingest skipped: %s", type(exc).__name__)
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
                    "filer_cik": row.filer_cik,
                    "filer_name": row.filer_name,
                    "report_date": row.report_date.isoformat(),
                    "cusip": row.cusip,
                    "ticker": row.ticker,
                    "shares": None if row.shares is None else str(row.shares),
                    "value_usd": None if row.value_usd is None else str(row.value_usd),
                }
                for row in rows
            ]
        ).encode("utf-8")
        store_raw_artifact(
            session,
            source_id=source.id,
            ingestion_run_id=run.id,
            source_url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR",
            payload=payload,
            storage_uri=object_store.store(
                f"raw/edgar/13f/{reference_date.isoformat()}.json",
                payload,
                content_type="application/json",
            ),
            filename=f"13f-{reference_date.isoformat()}.json",
            content_type="application/json",
            http_status=200,
            etag=None,
            last_modified=None,
            reference_date=reference_date,
        )
        for row in rows:
            action = upsert_thirteen_f_holding(
                session,
                filer_cik=row.filer_cik,
                filer_name=row.filer_name,
                report_date=row.report_date,
                cusip=row.cusip,
                ticker=row.ticker,
                shares=row.shares,
                value_usd=row.value_usd,
                source_id=source.id,
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
        logger.info("13F ingest holdings=%s inserted=%s", len(rows), inserted)
        return {
            "run_id": str(run.id),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "artifacts": 1,
            "status": run.status,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise
