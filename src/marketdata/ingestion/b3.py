import time
from datetime import date, timedelta
from logging import getLogger
from uuid import UUID

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
from marketdata.ingestion.checkpoint import (
    BackfillCheckpoint,
    load_checkpoint,
    save_checkpoint,
    should_resume,
)
from marketdata.ingestion.universe import (
    b3_equity_allowlist,
    live_otc_credit_enabled,
    should_persist_b3_equity_last,
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
from marketdata.providers.cotahist import (
    CotahistQuoteRecord,
    cotahist_year_url,
    fetch_cotahist_year,
    parse_cotahist_zip,
)
from marketdata.storage.models import InstrumentQuoteRow, InstrumentRow
from marketdata.storage.object_store import ObjectStorage, build_object_storage
from marketdata.storage.repositories import (
    attach_identifier,
    build_instrument_quote,
    cached_instrument_id,
    finish_ingestion_run,
    get_or_create_instrument_by_key,
    get_or_create_source,
    load_quote_keys,
    record_quality_event,
    start_ingestion_run,
    store_raw_artifact,
    upsert_quote,
)

B3_HOMEPAGE = (
    "https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/"
    "market-data/historico/boletins-diarios/pesquisa-por-pregao/pesquisa-por-pregao/"
)
logger = getLogger(__name__)


def _log_stage(stage: str, started: float | None = None, **fields: object) -> None:
    parts = [f"{key}={value}" for key, value in fields.items()]
    if started is not None:
        parts.insert(0, f"elapsed_ms={int((time.perf_counter() - started) * 1000)}")
    logger.info("b3 %s %s", stage, " ".join(parts))


def ingest_b3(
    session: Session,
    *,
    reference_date: date,
    storage: ObjectStorage | None = None,
    provider: B3Provider | None = None,
    price_payload: bytes | None = None,
    master_payload: bytes | None = None,
    derivatives_payload: bytes | None = None,
    credit_trades_payload: bytes | None = None,
    credit_master_payload: bytes | None = None,
) -> dict[str, int | str]:
    return _ingest_b3_day(
        session,
        reference_date=reference_date,
        storage=storage,
        provider=provider,
        price_payload=price_payload,
        master_payload=master_payload,
        derivatives_payload=derivatives_payload,
        credit_trades_payload=credit_trades_payload,
        credit_master_payload=credit_master_payload,
    )


def _ingest_b3_day(
    session: Session,
    *,
    reference_date: date,
    storage: ObjectStorage | None = None,
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
        allowlist = b3_equity_allowlist()
        _log_stage(
            "start",
            date=reference_date.isoformat(),
            equity_filter=allowlist is not None,
            allowlist=len(allowlist) if allowlist is not None else "all",
        )
        started = time.perf_counter()
        _log_stage("download start", kind="186")
        price_bytes, price_url, price_status = _load_file(
            b3, kind="186", reference_date=reference_date, payload=price_payload
        )
        _log_stage("download 186", started, bytes=len(price_bytes), http_status=price_status)
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
        started = time.perf_counter()
        quotes = parse_price_report(price_bytes)
        _log_stage("parse 186", started, records=len(quotes))
        instrument_ids: dict[str, UUID] = {}
        existing_quotes = load_quote_keys(session, source_id=source.id, on_date=reference_date)
        pending_quotes: list[InstrumentQuoteRow] = []
        started = time.perf_counter()
        for record in quotes:
            if not should_persist_b3_equity_last(record.ticker, allowlist):
                skipped += 1
                continue
            created = record.ticker not in instrument_ids
            instrument_id = cached_instrument_id(
                instrument_ids,
                session,
                source_id=source.id,
                source_key=record.ticker,
                asset_class=AssetClass.EQUITY,
                instrument_type="listed",
                name=record.ticker,
                currency=record.currency or "BRL",
            )
            if created:
                attach_identifier(
                    session,
                    instrument_id=instrument_id,
                    identifier_type=IdentifierType.TICKER,
                    identifier_value=record.ticker,
                    source_id=source.id,
                )
                if record.security_id:
                    attach_identifier(
                        session,
                        instrument_id=instrument_id,
                        identifier_type=IdentifierType.B3_SECURITY_ID,
                        identifier_value=record.security_id,
                        source_id=source.id,
                    )
            identity = (instrument_id, record.reference_date, PriceType.LAST.value)
            if identity in existing_quotes:
                skipped += 1
                continue
            pending_quotes.append(
                build_instrument_quote(
                    instrument_id=instrument_id,
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
            )
            existing_quotes.add(identity)
            inserted += 1
            if len(pending_quotes) >= 500:
                session.add_all(pending_quotes)
                session.flush()
                pending_quotes.clear()
        if pending_quotes:
            session.add_all(pending_quotes)
            session.flush()
            pending_quotes.clear()
        _log_stage(
            "persist 186",
            started,
            inserted=inserted,
            skipped=skipped,
            persisted_tickers=len(instrument_ids),
        )

        parsed = len(quotes)
        derivatives_bytes: bytes | None = None
        derivatives_url = pregao_url("187", reference_date)
        derivatives_status: int | None = None
        started = time.perf_counter()
        _log_stage("download start", kind="187")
        if derivatives_payload is not None:
            derivatives_bytes, derivatives_url, derivatives_status = _load_file(
                b3, kind="187", reference_date=reference_date, payload=derivatives_payload
            )
        elif price_payload is None:
            try:
                derivatives_bytes, derivatives_url, derivatives_status = _load_file(
                    b3, kind="187", reference_date=reference_date, payload=None
                )
            except (B3ParseError, httpx.HTTPError) as exc:
                _log_stage("skip 187", started, error=type(exc).__name__, detail=str(exc)[:200])
                derivatives_bytes = None
        if derivatives_bytes is not None:
            _log_stage(
                "download 187",
                started,
                bytes=len(derivatives_bytes),
                http_status=derivatives_status,
            )
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
            started = time.perf_counter()
            settlements = [
                record
                for record in parse_settlement_report(derivatives_bytes)
                if is_mvp_future_ticker(record.ticker)
            ]
            _log_stage("parse 187", started, mvp_records=len(settlements))
            parsed += len(settlements)
            started = time.perf_counter()
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
                instrument_ids[record.ticker] = instrument.id
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
            _log_stage("persist 187", started, mvp_records=len(settlements))

        master_bytes = master_payload
        master_url = pregao_url("028", reference_date)
        master_status: int | None = 200 if master_payload is not None else None
        started = time.perf_counter()
        _log_stage("download start", kind="028")
        if master_bytes is None:
            try:
                master_bytes, master_url, master_status = _load_file(
                    b3, kind="028", reference_date=reference_date, payload=None
                )
            except (B3ParseError, httpx.HTTPError) as exc:
                _log_stage("skip 028", started, error=type(exc).__name__, detail=str(exc)[:200])
                master_bytes = None
        if master_bytes is not None:
            _log_stage("download 028", started, bytes=len(master_bytes), http_status=master_status)
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
            keep = frozenset(instrument_ids)
            started = time.perf_counter()
            try:
                if keep:
                    master = parse_instrument_master(master_bytes, keep_tickers=keep)
                else:
                    master = {}
                    _log_stage("skip parse 028", started, reason="no_persisted_tickers")
            except B3ParseError as exc:
                _log_stage("skip parse 028", started, error=str(exc)[:200])
                rejected += 1
                master = {}
            else:
                matched = 0
                for ticker, info in master.items():
                    instrument_id = instrument_ids.get(ticker)
                    if instrument_id is None:
                        continue
                    matched += 1
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
                _log_stage("enrich 028", started, matched=matched, keep=len(keep))

        credit_live = live_otc_credit_enabled(allowlist) and price_payload is None
        if not live_otc_credit_enabled(allowlist) and credit_trades_payload is None:
            _log_stage("skip live OTC credit", reason="equity_universe_filter")
        started = time.perf_counter()
        if credit_live:
            _log_stage("download start", kind="otc_credit")
        credit_trades_bytes, credit_trades_url, credit_trades_status = _load_otc_table(
            b3,
            table_name=BDI_CREDIT_TRADES_TABLE,
            reference_date=reference_date,
            payload=credit_trades_payload,
            live=credit_live,
        )
        credit_master_bytes, credit_master_url, credit_master_status = _load_otc_table(
            b3,
            table_name=BDI_CREDIT_MASTER_TABLE,
            reference_date=reference_date,
            payload=credit_master_payload,
            live=credit_live,
        )
        if credit_live:
            _log_stage(
                "download otc_credit",
                started,
                trades_bytes=0 if credit_trades_bytes is None else len(credit_trades_bytes),
                master_bytes=0 if credit_master_bytes is None else len(credit_master_bytes),
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
            _log_stage("persist otc_trades", records=len(credit_trades))

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
            _log_stage("persist otc_master", records=len(cadastro))

        run.artifacts_downloaded = artifacts
        run.records_parsed = parsed
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_rejected = rejected
        run.records_normalized = inserted + updated + skipped
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        _log_stage(
            "done",
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            rejected=rejected,
            artifacts=artifacts,
        )
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
    except (B3ParseError, httpx.HTTPError) as exc:
        logger.info(
            "b3 skip %s error=%s detail=%s",
            table_name,
            type(exc).__name__,
            str(exc)[:200],
        )
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


def _is_empty_b3_day_error(exc: BaseException) -> bool:
    """Backfill-only: empty/holiday Pesquisa por Pregão ZIP is not a run failure."""
    return isinstance(exc, B3ParseError) and "not a usable zip" in str(exc).lower()


def _iter_calendar_days(start: date, end: date):
    day = start
    step = timedelta(days=1)
    while day <= end:
        yield day
        day += step


def _save_b3_checkpoint(
    store, start: date, end: date, last_completed: date | None, status: str
) -> None:
    save_checkpoint(
        store,
        BackfillCheckpoint(
            provider="b3",
            start=start.isoformat(),
            end=end.isoformat(),
            last_completed=last_completed.isoformat() if last_completed else None,
            status=status,
        ),
    )


def _prefer_vista_cotahist(
    existing: CotahistQuoteRecord, incoming: CotahistQuoteRecord
) -> CotahistQuoteRecord:
    if existing.extra.get("TPMERC") != "010" and incoming.extra.get("TPMERC") == "010":
        return incoming
    return existing


def _ensure_b3_source(session: Session):
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
    return source


def _ingest_cotahist_year(
    session: Session,
    *,
    year: int,
    start: date,
    end: date,
    storage: ObjectStorage | None,
    payload: bytes | None = None,
) -> dict[str, int]:
    object_store = storage or build_object_storage()
    source = _ensure_b3_source(session)
    run = start_ingestion_run(
        session,
        provider="b3",
        source_id=source.id,
        reference_date=min(end, date(year, 12, 31)),
    )
    inserted = updated = skipped = rejected = 0
    try:
        if payload is None:
            response = fetch_cotahist_year(year)
            zip_bytes = response.content
            source_url = (
                str(response.request.url)
                if response.request is not None
                else cotahist_year_url(year)
            )
            http_status = response.status_code
        else:
            zip_bytes = payload
            source_url = cotahist_year_url(year)
            http_status = 200
        storage_key = f"raw/b3/cotahist/year={year:04d}/COTAHIST_A{year}.ZIP"
        storage_uri = object_store.store(storage_key, zip_bytes, content_type="application/zip")
        artifact = store_raw_artifact(
            session,
            source_id=source.id,
            ingestion_run_id=run.id,
            source_url=source_url,
            payload=zip_bytes,
            storage_uri=storage_uri,
            filename=f"COTAHIST_A{year}.ZIP",
            content_type="application/zip",
            http_status=http_status,
            etag=None,
            last_modified=None,
            reference_date=min(end, date(year, 12, 31)),
        )
        by_key: dict[tuple[str, date], CotahistQuoteRecord] = {}
        for record in parse_cotahist_zip(zip_bytes):
            if record.reference_date < start or record.reference_date > end:
                continue
            key = (record.ticker, record.reference_date)
            existing = by_key.get(key)
            by_key[key] = record if existing is None else _prefer_vista_cotahist(existing, record)
        for index, record in enumerate(by_key.values(), start=1):
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
            if record.isin:
                attach_identifier(
                    session,
                    instrument_id=instrument.id,
                    identifier_type=IdentifierType.ISIN,
                    identifier_value=record.isin,
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
                is_official=True,
            )
            if action == "inserted":
                inserted += 1
            elif action == "updated":
                updated += 1
            else:
                skipped += 1
            if index % 1000 == 0:
                session.flush()
        run.artifacts_downloaded = 1
        run.records_parsed = len(by_key)
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_rejected = rejected
        run.records_normalized = inserted + updated + skipped
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        return {
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "rejected": rejected,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise


def backfill_b3(
    session,
    *,
    start: date,
    end: date,
    storage: ObjectStorage | None = None,
    provider: B3Provider | None = None,
    delay_seconds: float = 0.5,
    include_cotahist: bool = False,
    resume: bool = True,
) -> dict[str, int | str]:
    if end < start:
        raise ValueError("backfill_b3 end must be on or after start")
    object_store = storage or build_object_storage()
    effective_delay = 0.0 if provider is not None else delay_seconds
    checkpoint = load_checkpoint(object_store, "b3")
    resume_after: date | None = None
    if should_resume(checkpoint, start, end, resume=resume) and checkpoint is not None:
        if checkpoint.last_completed:
            resume_after = date.fromisoformat(checkpoint.last_completed)
    inserted = updated = skipped = rejected = artifacts = empty_days = 0
    last_completed: date | None = resume_after
    try:
        for day in _iter_calendar_days(start, end):
            if resume_after is not None and day <= resume_after:
                continue
            if day.weekday() >= 5:
                last_completed = day
                session.commit()
                _save_b3_checkpoint(object_store, start, end, last_completed=day, status="running")
                continue
            try:
                day_result = _ingest_b3_day(
                    session,
                    reference_date=day,
                    storage=object_store,
                    provider=provider,
                )
            except B3ParseError as exc:
                if not _is_empty_b3_day_error(exc):
                    raise
                session.rollback()
                empty_days += 1
            else:
                inserted += int(day_result["inserted"])
                updated += int(day_result["updated"])
                skipped += int(day_result["skipped"])
                rejected += int(day_result["rejected"])
                artifacts += int(day_result.get("artifacts", 0))
            last_completed = day
            session.commit()
            _save_b3_checkpoint(object_store, start, end, last_completed=day, status="running")
            if effective_delay > 0 and day < end:
                time.sleep(effective_delay)
        if include_cotahist:
            years = list(range(start.year, end.year + 1))
            for index, year in enumerate(years):
                year_result = _ingest_cotahist_year(
                    session,
                    year=year,
                    start=start,
                    end=end,
                    storage=object_store,
                )
                inserted += int(year_result["inserted"])
                updated += int(year_result["updated"])
                skipped += int(year_result["skipped"])
                rejected += int(year_result["rejected"])
                artifacts += 1
                session.commit()
                if effective_delay > 0 and index < len(years) - 1:
                    time.sleep(effective_delay)
        completed = last_completed or end
        _save_b3_checkpoint(object_store, start, end, last_completed=completed, status="succeeded")
        return {
            "status": "succeeded",
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "rejected": rejected,
            "empty_days": empty_days,
            "artifacts": artifacts,
        }
    except Exception:
        session.rollback()
        _save_b3_checkpoint(
            object_store, start, end, last_completed=last_completed, status="failed"
        )
        raise
