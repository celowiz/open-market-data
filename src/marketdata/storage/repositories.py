from datetime import UTC, date, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from marketdata.domain.enums import (
    AssetClass,
    IdentifierType,
    IngestionRunStatus,
    PriceType,
    QualityStatus,
    RedistributionPolicy,
)
from marketdata.providers.cvm import CvmDailyRecord
from marketdata.storage.models import (
    IngestionRunRow,
    InstrumentIdentifierRow,
    InstrumentQuoteRow,
    InstrumentRow,
    MarketSeriesObservationRow,
    MarketSeriesRow,
    RawArtifactRow,
    SourceRow,
)

CVM_SOURCE_NAME = "cvm"


def get_or_create_cvm_source(session: Session) -> SourceRow:
    row = session.scalar(select(SourceRow).where(SourceRow.name == CVM_SOURCE_NAME))
    if row is not None:
        return row
    row = SourceRow(
        id=uuid4(),
        name=CVM_SOURCE_NAME,
        display_name="CVM Dados Abertos",
        official=True,
        homepage="https://dados.cvm.gov.br/",
        documentation_url="https://dados.cvm.gov.br/dataset/fi-doc-inf_diario",
        data_license="ODbL-1.0",
        redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION.value,
        ingestion_enabled=True,
        public_api_enabled=True,
        public_dataset_enabled=True,
        notes="Informe Diário de Fundos. Attribution required.",
    )
    session.add(row)
    session.flush()
    return row


def start_ingestion_run(
    session: Session,
    *,
    provider: str,
    source_id: UUID,
    reference_date,
) -> IngestionRunRow:
    run = IngestionRunRow(
        id=uuid4(),
        provider=provider,
        source_id=source_id,
        started_at=datetime.now(UTC),
        requested_reference_date=reference_date,
        status=IngestionRunStatus.STARTED.value,
    )
    session.add(run)
    session.flush()
    return run


def finish_ingestion_run(run: IngestionRunRow, *, status: IngestionRunStatus) -> None:
    run.finished_at = datetime.now(UTC)
    run.status = status.value


def store_raw_artifact(
    session: Session,
    *,
    source_id: UUID,
    ingestion_run_id: UUID,
    source_url: str,
    payload: bytes,
    storage_uri: str,
    filename: str,
    content_type: str | None,
    http_status: int | None,
    etag: str | None,
    last_modified: str | None,
    reference_date,
) -> RawArtifactRow:
    digest = sha256(payload).hexdigest()
    existing = session.scalar(select(RawArtifactRow).where(RawArtifactRow.sha256 == digest))
    if existing is not None:
        storage_uri = existing.storage_uri
    artifact = RawArtifactRow(
        id=uuid4(),
        source_id=source_id,
        source_url=source_url,
        reference_date=reference_date,
        retrieved_at=datetime.now(UTC),
        content_type=content_type,
        filename=filename,
        http_status=http_status,
        etag=etag,
        last_modified=last_modified,
        sha256=digest,
        size_bytes=len(payload),
        storage_uri=storage_uri,
        ingestion_run_id=ingestion_run_id,
    )
    session.add(artifact)
    session.flush()
    return artifact


def get_or_create_fund_instrument(
    session: Session,
    *,
    source_id: UUID,
    record: CvmDailyRecord,
) -> InstrumentRow:
    source_key = f"{record.cnpj_fundo_classe}:{record.subclass_id or ''}"
    existing_id = session.scalar(
        select(InstrumentIdentifierRow.instrument_id).where(
            InstrumentIdentifierRow.identifier_type == IdentifierType.SOURCE_ID.value,
            InstrumentIdentifierRow.identifier_value == source_key,
            InstrumentIdentifierRow.source_id == source_id,
        )
    )
    if existing_id is not None:
        instrument = session.get(InstrumentRow, existing_id)
        if instrument is None:
            raise RuntimeError("instrument identifier points at a missing instrument")
        return instrument
    instrument = InstrumentRow(
        id=uuid4(),
        asset_class=AssetClass.FUND.value,
        instrument_type="fund_class",
        name=f"CVM fund {record.cnpj_fundo_classe}",
        currency="BRL",
        extra={"subclass_id": record.subclass_id} if record.subclass_id else {},
    )
    session.add(instrument)
    session.flush()
    session.add(
        InstrumentIdentifierRow(
            id=uuid4(),
            instrument_id=instrument.id,
            identifier_type=IdentifierType.SOURCE_ID.value,
            identifier_value=source_key,
            source_id=source_id,
        )
    )
    if record.subclass_id is None:
        session.add(
            InstrumentIdentifierRow(
                id=uuid4(),
                instrument_id=instrument.id,
                identifier_type=IdentifierType.CNPJ_FUNDO_CLASSE.value,
                identifier_value=record.cnpj_fundo_classe,
                source_id=source_id,
            )
        )
        session.add(
            InstrumentIdentifierRow(
                id=uuid4(),
                instrument_id=instrument.id,
                identifier_type=IdentifierType.CNPJ.value,
                identifier_value=record.cnpj_fundo_classe,
                source_id=source_id,
            )
        )
    else:
        session.add(
            InstrumentIdentifierRow(
                id=uuid4(),
                instrument_id=instrument.id,
                identifier_type=IdentifierType.CVM_SUBCLASS_ID.value,
                identifier_value=record.subclass_id,
                source_id=source_id,
            )
        )
    session.flush()
    return instrument


def upsert_fund_nav_quote(
    session: Session,
    *,
    instrument_id: UUID,
    source_id: UUID,
    record: CvmDailyRecord,
    artifact: RawArtifactRow,
    ingestion_run_id: UUID,
) -> str:
    latest = session.scalar(
        select(InstrumentQuoteRow)
        .where(
            InstrumentQuoteRow.instrument_id == instrument_id,
            InstrumentQuoteRow.reference_date == record.reference_date,
            InstrumentQuoteRow.source_id == source_id,
            InstrumentQuoteRow.price_type == PriceType.FUND_NAV.value,
        )
        .order_by(InstrumentQuoteRow.revision.desc())
    )
    if latest is not None:
        if latest.raw_artifact_id:
            previous_artifact = session.get(RawArtifactRow, latest.raw_artifact_id)
            if previous_artifact is not None and previous_artifact.sha256 == artifact.sha256:
                return "skipped"
        revision = latest.revision + 1
        action = "updated"
    else:
        revision = 1
        action = "inserted"

    session.add(
        InstrumentQuoteRow(
            id=uuid4(),
            instrument_id=instrument_id,
            reference_date=record.reference_date,
            value=record.quota_value,
            currency="BRL",
            unit="BRL_per_quota",
            price_type=PriceType.FUND_NAV.value,
            source_id=source_id,
            source_instrument_id=record.cnpj_fundo_classe,
            is_official=True,
            retrieved_at=artifact.retrieved_at,
            raw_artifact_id=artifact.id,
            ingestion_run_id=ingestion_run_id,
            revision=revision,
            quality_status=QualityStatus.OK.value,
            extra={
                "vl_patrim_liq": str(record.net_assets) if record.net_assets is not None else None,
                "schema_era": record.schema_era,
                "subclass_id": record.subclass_id,
            },
        )
    )
    return action


def resolve_instrument_id(session: Session, identifier: str) -> UUID | None:
    from marketdata.domain.identity import digits_only

    candidates = {identifier.strip(), digits_only(identifier)}
    candidates.discard("")
    row = session.scalar(
        select(InstrumentIdentifierRow).where(
            InstrumentIdentifierRow.identifier_value.in_(candidates)
        )
    )
    return row.instrument_id if row is not None else None


def get_or_create_source(
    session: Session,
    *,
    name: str,
    display_name: str,
    official: bool,
    homepage: str,
    documentation_url: str,
    data_license: str,
    redistribution_policy: RedistributionPolicy,
    public_api_enabled: bool,
    public_dataset_enabled: bool,
) -> SourceRow:
    row = session.scalar(select(SourceRow).where(SourceRow.name == name))
    if row is not None:
        return row
    row = SourceRow(
        id=uuid4(),
        name=name,
        display_name=display_name,
        official=official,
        homepage=homepage,
        documentation_url=documentation_url,
        data_license=data_license,
        redistribution_policy=redistribution_policy.value,
        ingestion_enabled=True,
        public_api_enabled=public_api_enabled,
        public_dataset_enabled=public_dataset_enabled,
    )
    session.add(row)
    session.flush()
    return row


def get_or_create_instrument_by_key(
    session: Session,
    *,
    source_id: UUID,
    source_key: str,
    asset_class: AssetClass,
    instrument_type: str,
    name: str,
    currency: str | None,
    maturity_date: date | None = None,
) -> InstrumentRow:
    existing_id = session.scalar(
        select(InstrumentIdentifierRow.instrument_id).where(
            InstrumentIdentifierRow.identifier_type == IdentifierType.SOURCE_ID.value,
            InstrumentIdentifierRow.identifier_value == source_key,
            InstrumentIdentifierRow.source_id == source_id,
        )
    )
    if existing_id is not None:
        instrument = session.get(InstrumentRow, existing_id)
        if instrument is None:
            raise RuntimeError("instrument identifier points at a missing instrument")
        return instrument
    instrument = InstrumentRow(
        id=uuid4(),
        asset_class=asset_class.value,
        instrument_type=instrument_type,
        name=name,
        currency=currency,
        maturity_date=maturity_date,
    )
    session.add(instrument)
    session.flush()
    session.add(
        InstrumentIdentifierRow(
            id=uuid4(),
            instrument_id=instrument.id,
            identifier_type=IdentifierType.SOURCE_ID.value,
            identifier_value=source_key,
            source_id=source_id,
        )
    )
    session.flush()
    return instrument


def upsert_quote(
    session: Session,
    *,
    instrument_id: UUID,
    source_id: UUID,
    reference_date: date,
    value,
    price_type: PriceType,
    artifact: RawArtifactRow,
    ingestion_run_id: UUID,
    currency: str | None,
    unit: str | None,
    extra: dict | None = None,
) -> str:
    latest = session.scalar(
        select(InstrumentQuoteRow)
        .where(
            InstrumentQuoteRow.instrument_id == instrument_id,
            InstrumentQuoteRow.reference_date == reference_date,
            InstrumentQuoteRow.source_id == source_id,
            InstrumentQuoteRow.price_type == price_type.value,
        )
        .order_by(InstrumentQuoteRow.revision.desc())
    )
    if latest is not None:
        if latest.raw_artifact_id:
            previous_artifact = session.get(RawArtifactRow, latest.raw_artifact_id)
            if previous_artifact is not None and previous_artifact.sha256 == artifact.sha256:
                return "skipped"
        revision = latest.revision + 1
        action = "updated"
    else:
        revision = 1
        action = "inserted"
    session.add(
        InstrumentQuoteRow(
            id=uuid4(),
            instrument_id=instrument_id,
            reference_date=reference_date,
            value=value,
            currency=currency,
            unit=unit,
            price_type=price_type.value,
            source_id=source_id,
            is_official=True,
            retrieved_at=artifact.retrieved_at,
            raw_artifact_id=artifact.id,
            ingestion_run_id=ingestion_run_id,
            revision=revision,
            quality_status=QualityStatus.OK.value,
            extra=extra or {},
        )
    )
    return action


def get_or_create_market_series(
    session: Session,
    *,
    source_id: UUID,
    code: str,
    source_series_id: str,
    name: str,
    unit: str,
) -> MarketSeriesRow:
    row = session.scalar(select(MarketSeriesRow).where(MarketSeriesRow.code == code))
    if row is not None:
        return row
    row = MarketSeriesRow(
        id=uuid4(),
        code=code,
        source_series_id=source_series_id,
        name=name,
        source_id=source_id,
        unit=unit,
        value_semantics=PriceType.REFERENCE.value,
    )
    session.add(row)
    session.flush()
    return row


def upsert_series_observation(
    session: Session,
    *,
    series_id: UUID,
    source_id: UUID,
    reference_date: date,
    value,
    artifact: RawArtifactRow,
    ingestion_run_id: UUID,
    extra: dict | None = None,
) -> str:
    latest = session.scalar(
        select(MarketSeriesObservationRow)
        .where(
            MarketSeriesObservationRow.series_id == series_id,
            MarketSeriesObservationRow.reference_date == reference_date,
            MarketSeriesObservationRow.source_id == source_id,
        )
        .order_by(MarketSeriesObservationRow.revision.desc())
    )
    if latest is not None:
        if latest.raw_artifact_id:
            previous_artifact = session.get(RawArtifactRow, latest.raw_artifact_id)
            if previous_artifact is not None and previous_artifact.sha256 == artifact.sha256:
                return "skipped"
        revision = latest.revision + 1
        action = "updated"
    else:
        revision = 1
        action = "inserted"
    session.add(
        MarketSeriesObservationRow(
            id=uuid4(),
            series_id=series_id,
            reference_date=reference_date,
            value=value,
            source_id=source_id,
            retrieved_at=artifact.retrieved_at,
            raw_artifact_id=artifact.id,
            ingestion_run_id=ingestion_run_id,
            revision=revision,
            quality_status=QualityStatus.OK.value,
            extra=extra or {},
        )
    )
    return action
