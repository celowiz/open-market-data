import json
from datetime import date, timedelta

from sqlalchemy.orm import Session

from marketdata.domain.enums import (
    AssetClass,
    IdentifierType,
    IngestionRunStatus,
    PriceType,
    RedistributionPolicy,
)
from marketdata.providers.yahoo import YahooProvider, YahooQuoteRecord
from marketdata.storage.object_store import LocalFileObjectStorage, build_object_storage
from marketdata.storage.repositories import (
    attach_identifier,
    finish_ingestion_run,
    get_or_create_instrument_by_key,
    get_or_create_source,
    start_ingestion_run,
    store_raw_artifact,
    upsert_quote,
)

DEFAULT_YAHOO_SYMBOLS = ["AAPL"]
YAHOO_HOMEPAGE = "https://finance.yahoo.com/"


def ingest_yahoo(
    session: Session,
    *,
    reference_date: date,
    symbols: list[str] | None = None,
    storage: LocalFileObjectStorage | None = None,
    provider: YahooProvider | None = None,
    history_rows: list[YahooQuoteRecord] | None = None,
) -> dict[str, int | str]:
    yahoo = provider or YahooProvider()
    object_store = storage or build_object_storage()
    requested = list(symbols) if symbols else list(DEFAULT_YAHOO_SYMBOLS)
    source = get_or_create_source(
        session,
        name="yahoo",
        display_name="Yahoo Finance",
        official=False,
        homepage=YAHOO_HOMEPAGE,
        documentation_url=YAHOO_HOMEPAGE,
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.UNKNOWN,
        public_api_enabled=False,
        public_dataset_enabled=False,
    )
    source.official = False
    source.redistribution_policy = RedistributionPolicy.UNKNOWN.value
    source.public_api_enabled = False
    source.public_dataset_enabled = False
    source.ingestion_enabled = True
    run = start_ingestion_run(
        session, provider=yahoo.name, source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = 0
    artifacts = 0
    parsed = 0
    try:
        for symbol in requested:
            if history_rows is not None:
                records = [
                    row
                    for row in history_rows
                    if row.symbol == symbol and row.reference_date == reference_date
                ]
            else:
                records = [
                    row
                    for row in yahoo.fetch_history(
                        symbol,
                        start=reference_date,
                        end=reference_date + timedelta(days=1),
                    )
                    if row.reference_date == reference_date
                ]
            if not records:
                continue
            payload_rows = [
                {
                    "symbol": record.symbol,
                    "date": record.reference_date.isoformat(),
                    "close": str(record.value),
                }
                for record in records
            ]
            payload = json.dumps(payload_rows, indent=None).encode("utf-8")
            key = (
                f"raw/yahoo/year={reference_date.year:04d}/"
                f"month={reference_date.month:02d}/"
                f"{symbol}-{reference_date.isoformat()}.json"
            )
            uri = object_store.store(key, payload, content_type="application/json")
            artifact = store_raw_artifact(
                session,
                source_id=source.id,
                ingestion_run_id=run.id,
                source_url=f"{YAHOO_HOMEPAGE}quote/{symbol}/history",
                payload=payload,
                storage_uri=uri,
                filename=f"{symbol}-{reference_date.isoformat()}.json",
                content_type="application/json",
                http_status=200,
                etag=None,
                last_modified=None,
                reference_date=reference_date,
            )
            artifacts += 1
            parsed += len(records)
            for record in records:
                instrument = get_or_create_instrument_by_key(
                    session,
                    source_id=source.id,
                    source_key=record.symbol,
                    asset_class=AssetClass.EQUITY,
                    instrument_type="equity",
                    name=record.symbol,
                    currency=record.currency,
                )
                attach_identifier(
                    session,
                    instrument_id=instrument.id,
                    identifier_type=IdentifierType.YAHOO_SYMBOL,
                    identifier_value=record.symbol,
                    source_id=source.id,
                )
                attach_identifier(
                    session,
                    instrument_id=instrument.id,
                    identifier_type=IdentifierType.TICKER,
                    identifier_value=record.symbol,
                    source_id=source.id,
                )
                action = upsert_quote(
                    session,
                    instrument_id=instrument.id,
                    source_id=source.id,
                    reference_date=record.reference_date,
                    value=record.value,
                    price_type=PriceType.CLOSE,
                    artifact=artifact,
                    ingestion_run_id=run.id,
                    currency=record.currency,
                    unit=record.currency,
                    extra={"source_field": record.source_field, "yahoo_symbol": record.symbol},
                    is_official=False,
                )
                if action == "inserted":
                    inserted += 1
                elif action == "updated":
                    updated += 1
                else:
                    skipped += 1
        run.artifacts_downloaded = artifacts
        run.records_parsed = parsed
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
            "artifacts": artifacts,
            "status": run.status,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise
