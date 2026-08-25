from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from marketdata.domain.enums import IdentifierType, IngestionRunStatus, PriceType
from marketdata.storage.models import (
    IngestionRunRow,
    InstrumentIdentifierRow,
    InstrumentQuoteRow,
    InstrumentRow,
    QualityEventRow,
    SourceRow,
)


@dataclass(frozen=True)
class SourceView:
    name: str
    ingestion_enabled: bool
    public_api_enabled: bool
    redistribution_policy: str


@dataclass(frozen=True)
class IdentifierHit:
    instrument_id: UUID
    identifier_type: str
    identifier_value: str
    source_name: str


@dataclass(frozen=True)
class StoredQuote:
    instrument_id: UUID
    reference_date: date
    value: Decimal
    price_type: PriceType
    source_name: str
    quality_status: str


class CoverageStore(Protocol):
    def source(self, name: str) -> SourceView | None: ...

    def instrument_exists(self, instrument_id: UUID) -> bool: ...

    def identifiers_for(
        self,
        *,
        values: list[str],
        types: list[str],
        source_name: str | None,
    ) -> list[IdentifierHit]: ...

    def quote(
        self,
        instrument_id: UUID,
        *,
        reference_date: date,
        price_type: PriceType,
        source_name: str,
    ) -> StoredQuote | None: ...

    def prior_quote_date(
        self,
        instrument_id: UUID,
        *,
        before: date,
        price_type: PriceType,
        source_name: str,
    ) -> date | None: ...

    def ingest_succeeded(self, source_name: str, reference_date: date) -> bool: ...

    def has_no_public_price(self, instrument_id: UUID, reference_date: date) -> bool: ...


@dataclass
class InMemoryCoverageStore:
    sources: dict[str, SourceView] = field(default_factory=dict)
    instruments: set[UUID] = field(default_factory=set)
    identifiers: list[IdentifierHit] = field(default_factory=list)
    quotes: list[StoredQuote] = field(default_factory=list)
    ingest_dates: set[tuple[str, date]] = field(default_factory=set)
    no_public_price: set[tuple[UUID, date]] = field(default_factory=set)

    def add_source(self, source: SourceView) -> None:
        self.sources[source.name] = source

    def add_instrument(self, instrument_id: UUID) -> None:
        self.instruments.add(instrument_id)

    def add_identifier(
        self,
        instrument_id: UUID,
        identifier_type: IdentifierType,
        identifier_value: str,
        source_name: str,
    ) -> None:
        self.identifiers.append(
            IdentifierHit(
                instrument_id=instrument_id,
                identifier_type=identifier_type.value,
                identifier_value=identifier_value,
                source_name=source_name,
            )
        )

    def add_quote(self, quote: StoredQuote) -> None:
        self.quotes.append(quote)

    def add_ingest(self, source_name: str, reference_date: date) -> None:
        self.ingest_dates.add((source_name, reference_date))

    def add_no_public_price(self, instrument_id: UUID, reference_date: date) -> None:
        self.no_public_price.add((instrument_id, reference_date))

    def source(self, name: str) -> SourceView | None:
        return self.sources.get(name)

    def instrument_exists(self, instrument_id: UUID) -> bool:
        return instrument_id in self.instruments

    def identifiers_for(
        self,
        *,
        values: list[str],
        types: list[str],
        source_name: str | None,
    ) -> list[IdentifierHit]:
        wanted_values = set(values)
        wanted_types = set(types)
        hits: list[IdentifierHit] = []
        for hit in self.identifiers:
            if hit.identifier_value not in wanted_values:
                continue
            if hit.identifier_type not in wanted_types:
                continue
            if source_name is not None and hit.source_name != source_name:
                continue
            hits.append(hit)
        return hits

    def quote(
        self,
        instrument_id: UUID,
        *,
        reference_date: date,
        price_type: PriceType,
        source_name: str,
    ) -> StoredQuote | None:
        matches = [
            item
            for item in self.quotes
            if item.instrument_id == instrument_id
            and item.reference_date == reference_date
            and item.price_type is price_type
            and item.source_name == source_name
        ]
        return matches[-1] if matches else None

    def prior_quote_date(
        self,
        instrument_id: UUID,
        *,
        before: date,
        price_type: PriceType,
        source_name: str,
    ) -> date | None:
        dates = [
            item.reference_date
            for item in self.quotes
            if item.instrument_id == instrument_id
            and item.reference_date < before
            and item.price_type is price_type
            and item.source_name == source_name
        ]
        return max(dates) if dates else None

    def ingest_succeeded(self, source_name: str, reference_date: date) -> bool:
        return (source_name, reference_date) in self.ingest_dates

    def has_no_public_price(self, instrument_id: UUID, reference_date: date) -> bool:
        return (instrument_id, reference_date) in self.no_public_price


_SUCCESSFUL_INGEST = (
    IngestionRunStatus.SUCCEEDED.value,
    IngestionRunStatus.PARTIAL.value,
)


class SessionCoverageStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def source(self, name: str) -> SourceView | None:
        row = self._session.scalar(select(SourceRow).where(SourceRow.name == name))
        if row is None:
            return None
        return SourceView(
            name=row.name,
            ingestion_enabled=row.ingestion_enabled,
            public_api_enabled=row.public_api_enabled,
            redistribution_policy=row.redistribution_policy,
        )

    def instrument_exists(self, instrument_id: UUID) -> bool:
        return self._session.get(InstrumentRow, instrument_id) is not None

    def identifiers_for(
        self,
        *,
        values: list[str],
        types: list[str],
        source_name: str | None,
    ) -> list[IdentifierHit]:
        stmt = (
            select(InstrumentIdentifierRow, SourceRow.name)
            .join(SourceRow, SourceRow.id == InstrumentIdentifierRow.source_id)
            .where(
                InstrumentIdentifierRow.identifier_value.in_(values),
                InstrumentIdentifierRow.identifier_type.in_(types),
            )
        )
        if source_name is not None:
            stmt = stmt.where(SourceRow.name == source_name)
        hits: list[IdentifierHit] = []
        for ident, name in self._session.execute(stmt):
            hits.append(
                IdentifierHit(
                    instrument_id=ident.instrument_id,
                    identifier_type=ident.identifier_type,
                    identifier_value=ident.identifier_value,
                    source_name=name,
                )
            )
        return hits

    def quote(
        self,
        instrument_id: UUID,
        *,
        reference_date: date,
        price_type: PriceType,
        source_name: str,
    ) -> StoredQuote | None:
        row = self._session.scalar(
            select(InstrumentQuoteRow)
            .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
            .where(
                InstrumentQuoteRow.instrument_id == instrument_id,
                InstrumentQuoteRow.reference_date == reference_date,
                InstrumentQuoteRow.price_type == price_type.value,
                SourceRow.name == source_name,
            )
            .order_by(InstrumentQuoteRow.revision.desc())
        )
        if row is None:
            return None
        text = format(Decimal(row.value), "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return StoredQuote(
            instrument_id=row.instrument_id,
            reference_date=row.reference_date,
            value=Decimal(text),
            price_type=PriceType(row.price_type),
            source_name=source_name,
            quality_status=row.quality_status,
        )

    def prior_quote_date(
        self,
        instrument_id: UUID,
        *,
        before: date,
        price_type: PriceType,
        source_name: str,
    ) -> date | None:
        return self._session.scalar(
            select(InstrumentQuoteRow.reference_date)
            .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
            .where(
                InstrumentQuoteRow.instrument_id == instrument_id,
                InstrumentQuoteRow.reference_date < before,
                InstrumentQuoteRow.price_type == price_type.value,
                SourceRow.name == source_name,
            )
            .order_by(InstrumentQuoteRow.reference_date.desc())
            .limit(1)
        )

    def ingest_succeeded(self, source_name: str, reference_date: date) -> bool:
        return (
            self._session.scalar(
                select(IngestionRunRow.id).where(
                    IngestionRunRow.provider == source_name,
                    IngestionRunRow.requested_reference_date == reference_date,
                    IngestionRunRow.status.in_(_SUCCESSFUL_INGEST),
                )
            )
            is not None
        )

    def has_no_public_price(self, instrument_id: UUID, reference_date: date) -> bool:
        wanted = reference_date.isoformat()
        events = self._session.scalars(
            select(QualityEventRow).where(
                QualityEventRow.instrument_id == instrument_id,
                QualityEventRow.event_type == "NO_PUBLIC_PRICE",
            )
        )
        return any(event.extra.get("reference_date") == wanted for event in events)
