from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class SourceRow(Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    homepage: Mapped[str | None] = mapped_column(String(512), nullable=True)
    documentation_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    data_license: Mapped[str | None] = mapped_column(String(128), nullable=True)
    redistribution_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    ingestion_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    public_api_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    public_dataset_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class InstrumentRow(Base):
    __tablename__ = "instruments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    asset_class: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mic: Mapped[str | None] = mapped_column(String(16), nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(256), nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    active_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    identifiers: Mapped[list["InstrumentIdentifierRow"]] = relationship(back_populates="instrument")
    quotes: Mapped[list["InstrumentQuoteRow"]] = relationship(back_populates="instrument")


class InstrumentIdentifierRow(Base):
    __tablename__ = "instrument_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "identifier_type",
            "identifier_value",
            "source_id",
            name="uq_instrument_identifiers_type_value_source",
        ),
        Index(
            "ix_instrument_identifiers_type_value",
            "identifier_type",
            "identifier_value",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("sources.id"), nullable=True, index=True
    )
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    instrument: Mapped[InstrumentRow] = relationship(back_populates="identifiers")


class IngestionRunRow(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    artifacts_downloaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_normalized: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)


class RawArtifactRow(Base):
    __tablename__ = "raw_artifacts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    encoding: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    etag: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    ingestion_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id"), nullable=True
    )


class InstrumentQuoteRow(Base):
    __tablename__ = "instrument_quotes"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "reference_date",
            "source_id",
            "price_type",
            "revision",
            name="uq_instrument_quotes_identity",
        ),
        Index(
            "ix_instrument_quotes_instrument_date",
            "instrument_id",
            "reference_date",
        ),
        Index("ix_instrument_quotes_source_date", "source_id", "reference_date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id"), nullable=False, index=True
    )
    reference_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(38, 16), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sources.id"), nullable=False, index=True
    )
    source_instrument_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("raw_artifacts.id"), nullable=True
    )
    ingestion_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id"), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    instrument: Mapped[InstrumentRow] = relationship(back_populates="quotes")


class MarketSeriesRow(Base):
    __tablename__ = "market_series"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_series_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    source_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    value_semantics: Mapped[str] = mapped_column(String(64), nullable=False, default="REFERENCE")
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)


class MarketSeriesObservationRow(Base):
    __tablename__ = "market_series_observations"
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "reference_date",
            "source_id",
            "revision",
            name="uq_market_series_observations_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    series_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("market_series.id"), nullable=False, index=True
    )
    reference_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(38, 16), nullable=False)
    source_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_artifact_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("raw_artifacts.id"), nullable=True
    )
    ingestion_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id"), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)


class QualityEventRow(Base):
    __tablename__ = "quality_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    ingestion_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id"), nullable=True, index=True
    )
    instrument_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("instruments.id"), nullable=True
    )
    source_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProviderStatusRow(Base):
    __tablename__ = "provider_status"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=True)
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_error: Mapped[str | None] = mapped_column(Text, nullable=True)
