from datetime import date

import httpx
from sqlalchemy.orm import Session

from marketdata.domain.enums import (
    AssetClass,
    IdentifierType,
    IngestionRunStatus,
    PriceType,
    RedistributionPolicy,
)
from marketdata.providers.b3 import (
    B3ParseError,
    B3Provider,
    parse_instrument_master,
    parse_price_report,
    pregao_url,
    validate_b3_zip,
)
from marketdata.storage.object_store import LocalFileObjectStorage, build_object_storage
from marketdata.storage.repositories import (
    attach_identifier,
    finish_ingestion_run,
    get_or_create_instrument_by_key,
    get_or_create_source,
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
        run.records_parsed = len(quotes)
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
                    if not info.isin:
                        continue
                    instrument_id = resolve_instrument_id(session, ticker)
                    if instrument_id is None:
                        continue
                    attach_identifier(
                        session,
                        instrument_id=instrument_id,
                        identifier_type=IdentifierType.ISIN,
                        identifier_value=info.isin,
                        source_id=source.id,
                    )

        run.artifacts_downloaded = artifacts
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
