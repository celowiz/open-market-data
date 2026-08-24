from datetime import date

from sqlalchemy.orm import Session

from marketdata.domain.enums import AssetClass, IngestionRunStatus, RedistributionPolicy
from marketdata.providers.tesouro import (
    TesouroProvider,
    parse_tesouro_csv,
    tesouro_instrument_key,
)
from marketdata.storage.object_store import LocalFileObjectStorage, build_object_storage
from marketdata.storage.repositories import (
    finish_ingestion_run,
    get_or_create_instrument_by_key,
    get_or_create_source,
    start_ingestion_run,
    store_raw_artifact,
    upsert_quote,
)


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
    source = get_or_create_source(
        session,
        name="tesouro",
        display_name="Tesouro Nacional",
        official=True,
        homepage="https://www.tesourotransparente.gov.br/",
        documentation_url="https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto",
        data_license="ODbL-1.0",
        redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )
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
        for record in records:
            instrument = get_or_create_instrument_by_key(
                session,
                source_id=source.id,
                source_key=tesouro_instrument_key(record.title_type, record.maturity_date),
                asset_class=AssetClass.GOVERNMENT_BOND,
                instrument_type=record.title_type,
                name=record.marketing_name,
                currency="BRL",
                maturity_date=record.maturity_date,
            )
            action = upsert_quote(
                session,
                instrument_id=instrument.id,
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
            if action == "inserted":
                inserted += 1
            elif action == "updated":
                updated += 1
            else:
                skipped += 1
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
