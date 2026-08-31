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
from marketdata.ingestion.checkpoint import BackfillCheckpoint, save_checkpoint
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
_UPSERT_FLUSH_EVERY = 1000


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
    source = _yahoo_source(session)
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


def _yahoo_source(session: Session):
    source = get_or_create_source(
        session,
        name="yahoo",
        display_name="Yahoo Finance",
        official=False,
        homepage=YAHOO_HOMEPAGE,
        documentation_url=YAHOO_HOMEPAGE,
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.UNKNOWN,
        public_api_enabled=True,
        public_dataset_enabled=False,
    )
    source.official = False
    source.redistribution_policy = RedistributionPolicy.UNKNOWN.value
    source.public_api_enabled = True
    source.public_dataset_enabled = False
    source.ingestion_enabled = True
    return source


def _records_for_symbol(
    *,
    symbol: str,
    start: date,
    end: date,
    yahoo: YahooProvider,
    history_rows: list[YahooQuoteRecord] | None,
) -> list[YahooQuoteRecord]:
    if history_rows is not None:
        candidates = history_rows
    else:
        candidates = yahoo.fetch_history(symbol, start=start, end=end + timedelta(days=1))
    return [
        row for row in candidates if row.symbol == symbol and start <= row.reference_date <= end
    ]


def _persist_yahoo_records(
    session: Session,
    *,
    records: list[YahooQuoteRecord],
    source,
    artifact,
    run_id,
    pending: int,
    flush_every: int = _UPSERT_FLUSH_EVERY,
) -> tuple[int, int, int, int]:
    inserted = updated = skipped = 0
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
            ingestion_run_id=run_id,
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
        pending += 1
        if pending >= flush_every:
            session.flush()
            pending = 0
    return inserted, updated, skipped, pending


def backfill_yahoo(
    session: Session,
    *,
    start: date,
    end: date,
    symbols: list[str] | None = None,
    storage: LocalFileObjectStorage | None = None,
    provider: YahooProvider | None = None,
    history_rows: list[YahooQuoteRecord] | None = None,
) -> dict[str, int | str]:
    yahoo = provider or YahooProvider()
    object_store = storage or build_object_storage()
    requested = list(symbols) if symbols else list(DEFAULT_YAHOO_SYMBOLS)
    source = _yahoo_source(session)
    run = start_ingestion_run(session, provider=yahoo.name, source_id=source.id, reference_date=end)
    inserted = updated = skipped = 0
    artifacts = 0
    parsed = 0
    pending = 0
    completed: str | None = None
    range_start = start.isoformat()
    range_end = end.isoformat()
    try:
        save_checkpoint(
            object_store,
            BackfillCheckpoint(
                provider="yahoo",
                start=range_start,
                end=range_end,
                last_completed=None,
                status="running",
            ),
        )
        for symbol in requested:
            records = _records_for_symbol(
                symbol=symbol,
                start=start,
                end=end,
                yahoo=yahoo,
                history_rows=history_rows,
            )
            if records:
                payload_rows = [
                    {
                        "symbol": record.symbol,
                        "date": record.reference_date.isoformat(),
                        "close": str(record.value),
                    }
                    for record in records
                ]
                payload = json.dumps(payload_rows, indent=None).encode("utf-8")
                key = f"raw/yahoo/backfill/{symbol}/{range_start}_{range_end}.json"
                uri = object_store.store(key, payload, content_type="application/json")
                artifact = store_raw_artifact(
                    session,
                    source_id=source.id,
                    ingestion_run_id=run.id,
                    source_url=f"{YAHOO_HOMEPAGE}quote/{symbol}/history",
                    payload=payload,
                    storage_uri=uri,
                    filename=f"{symbol}-{range_start}_{range_end}.json",
                    content_type="application/json",
                    http_status=200,
                    etag=None,
                    last_modified=None,
                    reference_date=end,
                )
                artifacts += 1
                parsed += len(records)
                add_ins, add_upd, add_skip, pending = _persist_yahoo_records(
                    session,
                    records=records,
                    source=source,
                    artifact=artifact,
                    run_id=run.id,
                    pending=pending,
                )
                inserted += add_ins
                updated += add_upd
                skipped += add_skip
            completed = symbol
            session.commit()
            save_checkpoint(
                object_store,
                BackfillCheckpoint(
                    provider="yahoo",
                    start=range_start,
                    end=range_end,
                    last_completed=completed,
                    status="running",
                ),
            )
        save_checkpoint(
            object_store,
            BackfillCheckpoint(
                provider="yahoo",
                start=range_start,
                end=range_end,
                last_completed=completed,
                status="succeeded",
            ),
        )
        run.artifacts_downloaded = artifacts
        run.records_parsed = parsed
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_normalized = inserted + updated + skipped
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.commit()
        return {
            "run_id": str(run.id),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "artifacts": artifacts,
            "status": run.status,
        }
    except Exception:
        save_checkpoint(
            object_store,
            BackfillCheckpoint(
                provider="yahoo",
                start=range_start,
                end=range_end,
                last_completed=completed,
                status="failed",
            ),
        )
        session.rollback()
        raise
