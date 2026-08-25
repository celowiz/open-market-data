from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from marketdata.domain.enums import (
    AssetClass,
    IdentifierType,
    IngestionRunStatus,
    PriceType,
    RedistributionPolicy,
)
from marketdata.providers.b3 import (
    BDI_CREDIT_MASTER_TABLE,
    BDI_CREDIT_TRADES_TABLE,
    BDI_EXPORT_URL,
    B3ParseError,
    B3Provider,
    is_mvp_future_ticker,
    otc_payload_has_rows,
    otc_payload_report_date,
    parse_instrument_master,
    parse_otc_instrument_file,
    parse_otc_trade_file,
    parse_price_report,
    parse_settlement_report,
    pregao_url,
    validate_b3_zip,
)
from marketdata.storage.models import InstrumentQuoteRow, InstrumentRow
from marketdata.storage.object_store import LocalFileObjectStorage, build_object_storage
from marketdata.storage.repositories import (
    attach_identifier,
    finish_ingestion_run,
    get_or_create_instrument_by_key,
    get_or_create_source,
    record_quality_event,
    resolve_instrument_id,
    start_ingestion_run,
    store_raw_artifact,
    upsert_quote,
)

B3_HOMEPAGE = (
    "https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/"
    "market-data/historico/boletins-diarios/pesquisa-por-pregao/pesquisa-por-pregao/"
)


def ingest_b3(
    session: Session,
    *,
    reference_date: date,
    storage: LocalFileObjectStorage | None = None,
    provider: B3Provider | None = None,
    price_payload: bytes | None = None,
    master_payload: bytes | None = None,
    derivatives_payload: bytes | None = None,
    credit_trades_payload: bytes | None = None,
    credit_master_payload: bytes | None = None,
) -> dict[str, int | str]:
    b3 = provider or B3Provider()
    object_store = storage or build_object_storage()
    source = get_or_create_source(
        session,
        name="b3",
        display_name="B3",
        official=True,
        homepage=B3_HOMEPAGE,
        documentation_url=B3_HOMEPAGE,
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.API_ONLY,
        public_api_enabled=True,
        public_dataset_enabled=False,
    )
    source.redistribution_policy = RedistributionPolicy.API_ONLY.value
    source.public_api_enabled = True
    source.public_dataset_enabled = False
    run = start_ingestion_run(
        session, provider=b3.name, source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = rejected = 0
    artifacts = 0
    try:
        price_bytes, price_url, price_status = _load_file(
            b3, kind="186", reference_date=reference_date, payload=price_payload
        )
        price_key = (
            f"raw/b3/year={reference_date.year:04d}/month={reference_date.month:02d}/"
            f"bvbg186_{reference_date.isoformat()}.zip"
        )
        price_uri = object_store.store(price_key, price_bytes, content_type="application/zip")
        artifact = store_raw_artifact(
            session,
            source_id=source.id,
            ingestion_run_id=run.id,
            source_url=price_url,
            payload=price_bytes,
            storage_uri=price_uri,
            filename=f"bvbg186_{reference_date.isoformat()}.zip",
            content_type="application/zip",
            http_status=price_status,
            etag=None,
            last_modified=None,
            reference_date=reference_date,
        )
        artifacts += 1
        quotes = parse_price_report(price_bytes)
        for index, record in enumerate(quotes, start=1):
            instrument = get_or_create_instrument_by_key(
                session,
                source_id=source.id,
                source_key=record.ticker,
                asset_class=AssetClass.EQUITY,
                instrument_type="listed",
                name=record.ticker,
                currency=record.currency or "BRL",
            )
            attach_identifier(
                session,
                instrument_id=instrument.id,
                identifier_type=IdentifierType.TICKER,
                identifier_value=record.ticker,
                source_id=source.id,
            )
            if record.security_id:
                attach_identifier(
                    session,
                    instrument_id=instrument.id,
                    identifier_type=IdentifierType.B3_SECURITY_ID,
                    identifier_value=record.security_id,
                    source_id=source.id,
                )
            action = upsert_quote(
                session,
                instrument_id=instrument.id,
                source_id=source.id,
                reference_date=record.reference_date,
                value=record.last_price,
                price_type=PriceType.LAST,
                artifact=artifact,
                ingestion_run_id=run.id,
                currency=record.currency or "BRL",
                unit="BRL",
                extra=record.extra,
            )
            if action == "inserted":
                inserted += 1
            elif action == "updated":
                updated += 1
            else:
                skipped += 1
            if index % 500 == 0:
                session.flush()

        parsed = len(quotes)
        derivatives_bytes: bytes | None = None
        derivatives_url = pregao_url("187", reference_date)
        derivatives_status: int | None = None
        if derivatives_payload is not None:
            derivatives_bytes, derivatives_url, derivatives_status = _load_file(
                b3, kind="187", reference_date=reference_date, payload=derivatives_payload
            )
        elif price_payload is None:
            try:
                derivatives_bytes, derivatives_url, derivatives_status = _load_file(
                    b3, kind="187", reference_date=reference_date, payload=None
                )
            except (B3ParseError, httpx.HTTPError):
                derivatives_bytes = None
        if derivatives_bytes is not None:
            derivatives_key = (
                f"raw/b3/year={reference_date.year:04d}/month={reference_date.month:02d}/"
                f"bvbg187_{reference_date.isoformat()}.zip"
            )
            derivatives_uri = object_store.store(
                derivatives_key, derivatives_bytes, content_type="application/zip"
            )
            settlement_artifact = store_raw_artifact(
                session,
                source_id=source.id,
                ingestion_run_id=run.id,
                source_url=derivatives_url,
                payload=derivatives_bytes,
                storage_uri=derivatives_uri,
                filename=f"bvbg187_{reference_date.isoformat()}.zip",
                content_type="application/zip",
                http_status=derivatives_status,
                etag=None,
                last_modified=None,
                reference_date=reference_date,
            )
            artifacts += 1
            settlements = [
                record
                for record in parse_settlement_report(derivatives_bytes)
                if is_mvp_future_ticker(record.ticker)
            ]
            parsed += len(settlements)
            for index, record in enumerate(settlements, start=1):
                instrument = get_or_create_instrument_by_key(
                    session,
                    source_id=source.id,
                    source_key=record.ticker,
                    asset_class=AssetClass.FUTURE,
                    instrument_type="future",
                    name=record.ticker,
                    currency=record.currency or "BRL",
                )
                attach_identifier(
                    session,
                    instrument_id=instrument.id,
                    identifier_type=IdentifierType.TICKER,
                    identifier_value=record.ticker,
                    source_id=source.id,
                )
                if record.security_id:
                    attach_identifier(
                        session,
                        instrument_id=instrument.id,
                        identifier_type=IdentifierType.B3_SECURITY_ID,
                        identifier_value=record.security_id,
                        source_id=source.id,
                    )
                action = upsert_quote(
                    session,
                    instrument_id=instrument.id,
                    source_id=source.id,
                    reference_date=record.reference_date,
                    value=record.settlement,
                    price_type=PriceType.OFFICIAL_SETTLEMENT,
                    artifact=settlement_artifact,
                    ingestion_run_id=run.id,
                    currency=record.currency or "BRL",
                    unit=record.unit,
                    extra=record.extra,
                )
                if action == "inserted":
                    inserted += 1
                elif action == "updated":
                    updated += 1
                else:
                    skipped += 1
                if index % 500 == 0:
                    session.flush()

        master_bytes = master_payload
        master_url = pregao_url("028", reference_date)
        master_status: int | None = 200 if master_payload is not None else None
        if master_bytes is None:
            try:
                master_bytes, master_url, master_status = _load_file(
                    b3, kind="028", reference_date=reference_date, payload=None
                )
            except (B3ParseError, httpx.HTTPError):
                master_bytes = None
        if master_bytes is not None:
            master_key = (
                f"raw/b3/year={reference_date.year:04d}/month={reference_date.month:02d}/"
                f"bvbg028_{reference_date.isoformat()}.zip"
            )
            master_uri = object_store.store(
                master_key, master_bytes, content_type="application/zip"
            )
            store_raw_artifact(
                session,
                source_id=source.id,
                ingestion_run_id=run.id,
                source_url=master_url,
                payload=master_bytes,
                storage_uri=master_uri,
                filename=f"bvbg028_{reference_date.isoformat()}.zip",
                content_type="application/zip",
                http_status=master_status,
                etag=None,
                last_modified=None,
                reference_date=reference_date,
            )
            artifacts += 1
            try:
                master = parse_instrument_master(master_bytes)
            except B3ParseError:
                rejected += 1
            else:
                for ticker, info in master.items():
                    instrument_id = resolve_instrument_id(session, ticker)
                    if instrument_id is None:
                        continue
                    if info.isin:
                        attach_identifier(
                            session,
                            instrument_id=instrument_id,
                            identifier_type=IdentifierType.ISIN,
                            identifier_value=info.isin,
                            source_id=source.id,
                        )
                    if info.maturity_date is not None:
                        instrument = session.get(InstrumentRow, instrument_id)
                        if instrument is not None and instrument.maturity_date is None:
                            instrument.maturity_date = info.maturity_date

        credit_trades_bytes, credit_trades_url, credit_trades_status = _load_otc_table(
            b3,
            table_name=BDI_CREDIT_TRADES_TABLE,
            reference_date=reference_date,
            payload=credit_trades_payload,
            live=price_payload is None,
        )
        credit_master_bytes, credit_master_url, credit_master_status = _load_otc_table(
            b3,
            table_name=BDI_CREDIT_MASTER_TABLE,
            reference_date=reference_date,
            payload=credit_master_payload,
            live=price_payload is None,
        )
        credit_quote_keys: set[tuple[str, date]] = set()
        if credit_trades_bytes is not None:
            trades_key = (
                f"raw/b3/year={reference_date.year:04d}/month={reference_date.month:02d}/"
                f"otc_trades_{reference_date.isoformat()}.json"
            )
            trades_uri = object_store.store(
                trades_key, credit_trades_bytes, content_type="application/json"
            )
            credit_artifact = store_raw_artifact(
                session,
                source_id=source.id,
                ingestion_run_id=run.id,
                source_url=credit_trades_url,
                payload=credit_trades_bytes,
                storage_uri=trades_uri,
                filename=f"otc_trades_{reference_date.isoformat()}.json",
                content_type="application/json",
                http_status=credit_trades_status,
                etag=None,
                last_modified=None,
                reference_date=reference_date,
            )
            artifacts += 1
            try:
                credit_trades = parse_otc_trade_file(credit_trades_bytes)
            except (B3ParseError, ValueError):
                rejected += 1
                credit_trades = []
            parsed += len(credit_trades)
            for index, record in enumerate(credit_trades, start=1):
                instrument = _upsert_credit_instrument(
                    session,
                    source_id=source.id,
                    ticker=record.ticker,
                    instrument_type=record.instrument_type,
                    name=record.name or record.ticker,
                    isin=record.isin,
                    maturity_date=None,
                )
                action = upsert_quote(
                    session,
                    instrument_id=instrument.id,
                    source_id=source.id,
                    reference_date=record.reference_date,
                    value=record.last_price,
                    price_type=PriceType.LAST,
                    artifact=credit_artifact,
                    ingestion_run_id=run.id,
                    currency="BRL",
                    unit="BRL",
                    extra=record.extra,
                )
                credit_quote_keys.add((record.ticker, record.reference_date))
                if action == "inserted":
                    inserted += 1
                elif action == "updated":
                    updated += 1
                else:
                    skipped += 1
                if index % 500 == 0:
                    session.flush()

        if credit_master_bytes is not None:
            master_otc_key = (
                f"raw/b3/year={reference_date.year:04d}/month={reference_date.month:02d}/"
                f"otc_instruments_{reference_date.isoformat()}.json"
            )
            master_otc_uri = object_store.store(
                master_otc_key, credit_master_bytes, content_type="application/json"
            )
            store_raw_artifact(
                session,
                source_id=source.id,
                ingestion_run_id=run.id,
                source_url=credit_master_url,
                payload=credit_master_bytes,
                storage_uri=master_otc_uri,
                filename=f"otc_instruments_{reference_date.isoformat()}.json",
                content_type="application/json",
                http_status=credit_master_status,
                etag=None,
                last_modified=None,
                reference_date=reference_date,
            )
            artifacts += 1
            try:
                cadastro = parse_otc_instrument_file(credit_master_bytes)
            except (B3ParseError, ValueError):
                rejected += 1
                cadastro = []
            for record in cadastro:
                instrument = _upsert_credit_instrument(
                    session,
                    source_id=source.id,
                    ticker=record.ticker,
                    instrument_type=record.instrument_type,
                    name=record.name or record.ticker,
                    isin=record.isin,
                    maturity_date=record.maturity_date,
                )
                if _should_record_credit_absence(
                    reference_date=reference_date,
                    trades_payload=credit_trades_bytes,
                ):
                    absence_date = _credit_absence_date(
                        credit_trades_bytes, fallback=reference_date
                    )
                    has_quote = (record.ticker, absence_date) in credit_quote_keys
                    if not has_quote:
                        existing_quote = session.scalar(
                            select(InstrumentQuoteRow.id).where(
                                InstrumentQuoteRow.instrument_id == instrument.id,
                                InstrumentQuoteRow.source_id == source.id,
                                InstrumentQuoteRow.reference_date == absence_date,
                                InstrumentQuoteRow.price_type == PriceType.LAST.value,
                            )
                        )
                        has_quote = existing_quote is not None
                    if not has_quote:
                        record_quality_event(
                            session,
                            ingestion_run_id=run.id,
                            instrument_id=instrument.id,
                            source_id=source.id,
                            event_type="NO_PUBLIC_PRICE",
                            message=(
                                f"No public last price for {record.ticker} "
                                f"on {absence_date.isoformat()}"
                            ),
                            extra={
                                "reference_date": absence_date.isoformat(),
                                "ticker": record.ticker,
                            },
                        )

        run.artifacts_downloaded = artifacts
        run.records_parsed = parsed
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_rejected = rejected
        run.records_normalized = inserted + updated + skipped
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        return {
            "run_id": str(run.id),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "rejected": rejected,
            "artifacts": artifacts,
            "status": run.status,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise


def _load_file(
    provider: B3Provider,
    *,
    kind: str,
    reference_date: date,
    payload: bytes | None,
) -> tuple[bytes, str, int]:
    if payload is not None:
        validate_b3_zip(payload)
        return payload, pregao_url(kind, reference_date), 200
    response = provider.fetch(kind, reference_date)
    url = (
        str(response.request.url)
        if response.request is not None
        else pregao_url(kind, reference_date)
    )
    return response.content, url, response.status_code


def _load_otc_table(
    provider: B3Provider,
    *,
    table_name: str,
    reference_date: date,
    payload: bytes | None,
    live: bool,
) -> tuple[bytes | None, str, int | None]:
    url = BDI_EXPORT_URL
    if payload is not None:
        return payload, url, 200
    if not live:
        return None, url, None
    try:
        response = provider.fetch_public_table(table_name, reference_date)
    except (B3ParseError, httpx.HTTPError):
        return None, url, None
    response_url = str(response.request.url) if response.request is not None else url
    return response.content, response_url, response.status_code


def _upsert_credit_instrument(
    session: Session,
    *,
    source_id,
    ticker: str,
    instrument_type: str,
    name: str,
    isin: str | None,
    maturity_date: date | None,
) -> InstrumentRow:
    instrument = get_or_create_instrument_by_key(
        session,
        source_id=source_id,
        source_key=ticker,
        asset_class=AssetClass.CREDIT,
        instrument_type=instrument_type,
        name=name,
        currency="BRL",
        maturity_date=maturity_date,
    )
    if maturity_date is not None and instrument.maturity_date is None:
        instrument.maturity_date = maturity_date
    attach_identifier(
        session,
        instrument_id=instrument.id,
        identifier_type=IdentifierType.TICKER,
        identifier_value=ticker,
        source_id=source_id,
    )
    if isin:
        attach_identifier(
            session,
            instrument_id=instrument.id,
            identifier_type=IdentifierType.ISIN,
            identifier_value=isin,
            source_id=source_id,
        )
    return instrument


def _should_record_credit_absence(*, reference_date: date, trades_payload: bytes | None) -> bool:
    if trades_payload is None or not trades_payload.strip():
        return False
    if reference_date.weekday() >= 5:
        return False
    return otc_payload_has_rows(trades_payload)


def _credit_absence_date(trades_payload: bytes | None, *, fallback: date) -> date:
    if trades_payload is None:
        return fallback
    return otc_payload_report_date(trades_payload) or fallback
