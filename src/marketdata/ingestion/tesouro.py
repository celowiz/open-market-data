from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from marketdata.domain.enums import AssetClass, IngestionRunStatus, RedistributionPolicy
from marketdata.ingestion.checkpoint import (
    BackfillCheckpoint,
    load_checkpoint,
    save_checkpoint,
    should_resume,
)
from marketdata.providers.tesouro import (
    TesouroProvider,
    TesouroQuoteRecord,
    parse_tesouro_csv,
    tesouro_instrument_key,
)
from marketdata.storage.models import IngestionRunRow, InstrumentQuoteRow, RawArtifactRow, SourceRow
from marketdata.storage.object_store import LocalFileObjectStorage, build_object_storage
from marketdata.storage.repositories import (
    build_instrument_quote,
    cached_instrument_id,
    finish_ingestion_run,
    get_or_create_source,
    load_quote_keys,
    start_ingestion_run,
    store_raw_artifact,
)

_TESOURO_FLUSH_EVERY = 1000


def _tesouro_source(session: Session) -> SourceRow:
    return get_or_create_source(
        session,
        name="tesouro",
        display_name="Tesouro Nacional",
        official=True,
        homepage="https://www.tesourotransparente.gov.br/",
        documentation_url=(
            "https://www.tesourotransparente.gov.br/ckan/dataset/"
            "taxas-dos-titulos-ofertados-pelo-tesouro-direto"
        ),
        data_license="ODbL-1.0",
        redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )


def _upsert_tesouro_records(
    session: Session,
    *,
    records: list[TesouroQuoteRecord],
    source: SourceRow,
    artifact: RawArtifactRow,
    run: IngestionRunRow,
    flush_every: int | None = None,
) -> tuple[int, int, int]:
    inserted = updated = skipped = 0
    instrument_ids: dict[str, UUID] = {}
    existing = load_quote_keys(session, source_id=source.id)
    pending: list[InstrumentQuoteRow] = []
    batch = flush_every if flush_every is not None and flush_every > 0 else len(records) or 1

    def _flush_pending() -> None:
        if not pending:
            return
        session.add_all(pending)
        session.flush()
        session.commit()
        pending.clear()

    for record in records:
        source_key = tesouro_instrument_key(record.title_type, record.maturity_date)
        instrument_id = cached_instrument_id(
            instrument_ids,
            session,
            source_id=source.id,
            source_key=source_key,
            asset_class=AssetClass.GOVERNMENT_BOND,
            instrument_type=record.title_type,
            name=record.marketing_name,
            currency="BRL",
            maturity_date=record.maturity_date,
        )
        identity = (instrument_id, record.reference_date, record.price_type.value)
        if identity in existing:
            skipped += 1
            continue
        pending.append(
            build_instrument_quote(
                instrument_id=instrument_id,
                source_id=source.id,
                reference_date=record.reference_date,
                value=record.value,
                price_type=record.price_type,
                artifact=artifact,
                ingestion_run_id=run.id,
                currency="BRL" if record.unit == "BRL" else None,
                unit=record.unit,
                extra={"source_field": record.source_field, "title_type": record.title_type},
            )
        )
        existing.add(identity)
        inserted += 1
        if len(pending) >= batch:
            _flush_pending()
    _flush_pending()
    return inserted, updated, skipped


def ingest_tesouro(
    session: Session,
    *,
    reference_date: date,
    storage: LocalFileObjectStorage | None = None,
    provider: TesouroProvider | None = None,
    csv_text: str | None = None,
) -> dict[str, int | str]:
    tesouro = provider or TesouroProvider()
    object_store = storage or build_object_storage()
    source = _tesouro_source(session)
    run = start_ingestion_run(
        session, provider=tesouro.name, source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = rejected = 0
    try:
        if csv_text is None:
            response = tesouro.fetch_csv()
            payload = response.content
            url = str(response.request.url) if response.request is not None else tesouro.csv_url()
            http_status = response.status_code
            content_type = response.headers.get("content-type")
        else:
            payload = csv_text.encode("utf-8")
            url = tesouro.csv_url()
            http_status = 200
            content_type = "text/csv"
        key = (
            f"raw/tesouro/year={reference_date.year:04d}/"
            f"month={reference_date.month:02d}/precotaxatesourodireto.csv"
        )
        uri = object_store.store(key, payload, content_type="text/csv")
        artifact = store_raw_artifact(
            session,
            source_id=source.id,
            ingestion_run_id=run.id,
            source_url=url,
            payload=payload,
            storage_uri=uri,
            filename="precotaxatesourodireto.csv",
            content_type=content_type,
            http_status=http_status,
            etag=None,
            last_modified=None,
            reference_date=reference_date,
        )
        text = payload.decode("latin-1")
        records = parse_tesouro_csv(text, reference_date=reference_date)
        run.records_parsed = len(records)
        inserted, updated, skipped = _upsert_tesouro_records(
            session,
            records=records,
            source=source,
            artifact=artifact,
            run=run,
        )
        run.artifacts_downloaded = 1
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
            "status": run.status,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise


def backfill_tesouro(
    session: Session,
    *,
    start: date,
    end: date,
    storage: LocalFileObjectStorage | None = None,
    provider: TesouroProvider | None = None,
    csv_text: str | None = None,
    resume: bool = True,
) -> dict[str, int | str]:
    tesouro = provider or TesouroProvider()
    object_store = storage or build_object_storage()
    existing = load_checkpoint(object_store, tesouro.name)
    if (
        should_resume(existing, start, end, resume=resume)
        and existing is not None
        and existing.status == "succeeded"
    ):
        return {
            "run_id": "",
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "status": existing.status,
        }

    source = _tesouro_source(session)
    run = start_ingestion_run(
        session, provider=tesouro.name, source_id=source.id, reference_date=end
    )
    inserted = updated = skipped = rejected = 0
    try:
        if csv_text is None:
            response = tesouro.fetch_csv()
            payload = response.content
            url = str(response.request.url) if response.request is not None else tesouro.csv_url()
            http_status = response.status_code
            content_type = response.headers.get("content-type")
        else:
            payload = csv_text.encode("utf-8")
            url = tesouro.csv_url()
            http_status = 200
            content_type = "text/csv"
        filename = f"precotaxatesourodireto-{start.isoformat()}_{end.isoformat()}.csv"
        key = f"raw/tesouro/backfill/{filename}"
        uri = object_store.store(key, payload, content_type="text/csv")
        artifact = store_raw_artifact(
            session,
            source_id=source.id,
            ingestion_run_id=run.id,
            source_url=url,
            payload=payload,
            storage_uri=uri,
            filename=filename,
            content_type=content_type,
            http_status=http_status,
            etag=None,
            last_modified=None,
            reference_date=end,
        )
        text = payload.decode("latin-1")
        records = [
            record
            for record in parse_tesouro_csv(text, reference_date=None)
            if start <= record.reference_date <= end
        ]
        run.records_parsed = len(records)
        inserted, updated, skipped = _upsert_tesouro_records(
            session,
            records=records,
            source=source,
            artifact=artifact,
            run=run,
            flush_every=_TESOURO_FLUSH_EVERY,
        )
        run.artifacts_downloaded = 1
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_rejected = rejected
        run.records_normalized = inserted + updated + skipped
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        session.commit()
        save_checkpoint(
            object_store,
            BackfillCheckpoint(
                provider=tesouro.name,
                start=start.isoformat(),
                end=end.isoformat(),
                last_completed=end.isoformat(),
                status="succeeded",
            ),
        )
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
