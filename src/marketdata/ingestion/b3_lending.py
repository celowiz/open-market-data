from __future__ import annotations

from datetime import date
from logging import getLogger

import httpx
from sqlalchemy.orm import Session

from marketdata.config import get_settings
from marketdata.datasets.parquet import write_parquet_bytes
from marketdata.domain.enums import AssetClass, IdentifierType, IngestionRunStatus
from marketdata.ingestion.b3 import _ensure_b3_source
from marketdata.ingestion.universe import lending_equity_allowlist
from marketdata.providers.b3 import B3ParseError, B3Provider
from marketdata.providers.b3_lending import (
    BDI_OPEN_POSITION_TABLE,
    BDI_REGISTERED_TABLE_CANDIDATES,
    LENDING_OPEN_POSITION,
    LENDING_REGISTERED,
    negociosbtb_urls,
    parse_lending_table,
    parse_negociosbtb_tape,
)
from marketdata.storage.object_store import (
    build_object_storage,
    public_publication_storage_configured,
)
from marketdata.storage.repositories import (
    attach_identifier,
    finish_ingestion_run,
    get_or_create_instrument_by_key,
    resolve_instrument_id,
    start_ingestion_run,
    store_raw_artifact,
    upsert_lending_snapshot,
)

logger = getLogger(__name__)


def ingest_b3_lending(
    session: Session,
    *,
    reference_date: date,
    registered_payload: bytes | None = None,
    open_payload: bytes | None = None,
    negociosbtb_payload: bytes | None = None,
    provider: B3Provider | None = None,
) -> dict[str, int | str]:
    b3 = provider or B3Provider()
    object_store = build_object_storage()
    source = _ensure_b3_source(session)
    allowlist = lending_equity_allowlist()
    run = start_ingestion_run(
        session, provider="b3-lending", source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = artifacts = 0
    try:
        registered_bytes, registered_url, registered_status = _load_registered(
            b3, reference_date=reference_date, payload=registered_payload
        )
        open_bytes, open_url, open_status = _load_open(
            b3, reference_date=reference_date, payload=open_payload
        )
        for payload, url, status, snapshot_type, filename in (
            (
                registered_bytes,
                registered_url,
                registered_status,
                LENDING_REGISTERED,
                f"b3-lending-registered-{reference_date.isoformat()}.json",
            ),
            (
                open_bytes,
                open_url,
                open_status,
                LENDING_OPEN_POSITION,
                f"b3-lending-open-{reference_date.isoformat()}.json",
            ),
        ):
            if payload is None:
                logger.info(
                    "b3-lending skip snapshot=%s date=%s (HTTP 404/empty or missing table)",
                    snapshot_type,
                    reference_date,
                )
                skipped += 1
                continue
            artifact = store_raw_artifact(
                session,
                source_id=source.id,
                ingestion_run_id=run.id,
                source_url=url,
                payload=payload,
                storage_uri=object_store.store(
                    f"raw/b3/lending/{snapshot_type}/{reference_date.isoformat()}",
                    payload,
                    content_type="application/json",
                ),
                filename=filename,
                content_type="application/json",
                http_status=status,
                etag=None,
                last_modified=None,
                reference_date=reference_date,
            )
            artifacts += 1
            records = parse_lending_table(
                payload,
                snapshot_type=snapshot_type,
                reference_date=reference_date,
                allowlist=allowlist,
            )
            for record in records:
                instrument_id = _lending_instrument_id(
                    session, source_id=source.id, ticker=record.ticker
                )
                action = upsert_lending_snapshot(
                    session,
                    ticker=record.ticker,
                    instrument_id=instrument_id,
                    reference_date=record.reference_date,
                    snapshot_type=record.snapshot_type,
                    source_id=source.id,
                    qty=record.qty,
                    avg_rate=record.avg_rate,
                    contracts=record.contracts,
                    avg_price=record.avg_price,
                    balance_brl=record.balance_brl,
                    market=record.market,
                    artifact=artifact,
                    ingestion_run_id=run.id,
                    extra=record.extra,
                )
                if action == "inserted":
                    inserted += 1
                elif action == "updated":
                    updated += 1
                else:
                    skipped += 1
        parquet_status = _maybe_publish_negociosbtb(
            b3,
            reference_date=reference_date,
            payload=negociosbtb_payload,
            object_store=object_store,
            allowlist=allowlist,
        )
        run.artifacts_downloaded = artifacts
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_normalized = inserted + updated
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        return {
            "run_id": str(run.id),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "artifacts": artifacts,
            "status": run.status,
            "negociosbtb": parquet_status,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise


def _lending_instrument_id(session: Session, *, source_id, ticker: str):
    existing = resolve_instrument_id(session, ticker)
    if existing is not None:
        return existing
    instrument = get_or_create_instrument_by_key(
        session,
        source_id=source_id,
        source_key=f"b3-lending:{ticker}",
        asset_class=AssetClass.EQUITY,
        instrument_type="listed_share",
        name=ticker,
        currency="BRL",
    )
    attach_identifier(
        session,
        instrument_id=instrument.id,
        identifier_type=IdentifierType.TICKER,
        identifier_value=ticker,
        source_id=source_id,
    )
    return instrument.id


def _load_registered(
    provider: B3Provider, *, reference_date: date, payload: bytes | None
) -> tuple[bytes | None, str, int | None]:
    if payload is not None:
        return payload, "fixture://b3-lending-registered", 200
    last_url = ""
    for table in BDI_REGISTERED_TABLE_CANDIDATES:
        last_url = f"bdi:{table}"
        content, status = _fetch_bdi_table(provider, table, reference_date)
        if content is not None:
            return content, last_url, status
    return None, last_url, None


def _load_open(
    provider: B3Provider, *, reference_date: date, payload: bytes | None
) -> tuple[bytes | None, str, int | None]:
    if payload is not None:
        return payload, "fixture://b3-lending-open", 200
    content, status = _fetch_bdi_table(provider, BDI_OPEN_POSITION_TABLE, reference_date)
    return content, f"bdi:{BDI_OPEN_POSITION_TABLE}", status


def _fetch_bdi_table(
    provider: B3Provider, table_name: str, reference_date: date
) -> tuple[bytes | None, int | None]:
    try:
        response = provider.fetch_public_table(table_name, reference_date)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        if status in {400, 404, 422}:
            logger.info("b3-lending skip table=%s status=%s", table_name, status)
            return None, status
        raise
    except (B3ParseError, httpx.HTTPError) as exc:
        logger.info("b3-lending skip table=%s error=%s", table_name, type(exc).__name__)
        return None, None
    return response.content, response.status_code


def _maybe_publish_negociosbtb(
    provider: B3Provider,
    *,
    reference_date: date,
    payload: bytes | None,
    object_store,
    allowlist: frozenset[str],
) -> str:
    settings = get_settings()
    if not public_publication_storage_configured(settings):
        logger.info("NEGOCIOSBTB parquet skipped: object storage is not s3 (R2 is not configured).")
        return "skipped"
    body = payload
    if body is None:
        for url in negociosbtb_urls(reference_date):
            try:
                response = httpx.get(
                    url,
                    timeout=30.0,
                    follow_redirects=True,
                    headers={"User-Agent": settings.http_user_agent},
                )
            except httpx.HTTPError as exc:
                logger.info("NEGOCIOSBTB skip url=%s error=%s", url, type(exc).__name__)
                continue
            if response.status_code in {400, 404}:
                logger.info("NEGOCIOSBTB skip url=%s status=%s", url, response.status_code)
                continue
            if response.status_code >= 400:
                continue
            body = response.content
            break
    if body is None:
        return "skipped"
    try:
        rows = parse_negociosbtb_tape(body)
    except B3ParseError as exc:
        logger.info("NEGOCIOSBTB parse skipped: %s", exc)
        return "skipped"
    filtered = [
        row
        for row in rows
        if str(row.get("TCKR_SYMB") or row.get("Ticker") or "").upper() in allowlist
    ]
    if not filtered:
        logger.info("NEGOCIOSBTB parquet skipped: no scratch tickers date=%s", reference_date)
        return "skipped"
    try:
        import polars as pl

        payload_out = write_parquet_bytes(pl.DataFrame(filtered, infer_schema_length=0))
    except Exception as exc:
        logger.info("NEGOCIOSBTB parquet skipped: %s", type(exc).__name__)
        return "skipped"
    object_store.store(
        f"curated/b3/negociosbtb/date={reference_date.isoformat()}/tape.parquet",
        payload_out,
        content_type="application/vnd.apache.parquet",
    )
    logger.info("NEGOCIOSBTB stored rows=%s date=%s", len(filtered), reference_date)
    return "stored"
