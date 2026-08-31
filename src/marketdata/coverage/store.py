from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from marketdata.coverage.csv import UniverseRow
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


def _decimal_value(value: object) -> Decimal:
    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return Decimal(text)


class SessionCoverageStore:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._prefetch_date: date | None = None
        self._source_cache: dict[str, SourceView] | None = None
        self._identifier_hits: list[IdentifierHit] | None = None
        self._instrument_ids: set[UUID] | None = None
        self._quotes: dict[tuple[UUID, str, str], StoredQuote] | None = None
        self._prior_dates: dict[tuple[UUID, str, str], date] | None = None
        self._ingest_ok: set[tuple[str, date]] | None = None
        self._no_public: set[tuple[UUID, date]] | None = None

    def prefetch_universe(self, rows: Sequence[UniverseRow], reference_date: date) -> None:
        from marketdata.coverage.resolve import resolve_row

        self._prefetch_date = reference_date
        names = sorted({row.preferred_provider for row in rows if row.preferred_provider})
        self._load_sources(names)
        values: list[str] = []
        for row in rows:
            if row.instrument_id is not None:
                continue
            if row.isin:
                values.append(row.isin)
            ticker = row.ticker.strip()
            if ticker:
                values.append(ticker)
        self._load_identifiers(values)
        uuid_ids = [row.instrument_id for row in rows if row.instrument_id is not None]
        self._load_existing_instruments(uuid_ids)
        resolved: list[UUID] = []
        for row in rows:
            resolved.extend(resolve_row(row, self))
        unique_ids = list(dict.fromkeys(resolved))
        self._load_quotes(unique_ids, reference_date)
        self._load_prior_dates(unique_ids, reference_date)
        self._load_ingest(names, reference_date)
        self._load_no_public(unique_ids, reference_date)

    def _load_sources(self, names: list[str]) -> None:
        self._source_cache = {}
        if not names:
            return
        for row in self._session.scalars(select(SourceRow).where(SourceRow.name.in_(names))):
            self._source_cache[row.name] = SourceView(
                name=row.name,
                ingestion_enabled=row.ingestion_enabled,
                public_api_enabled=row.public_api_enabled,
                redistribution_policy=row.redistribution_policy,
            )

    def _load_identifiers(self, values: list[str]) -> None:
        self._identifier_hits = []
        unique_values = list(dict.fromkeys(values))
        if not unique_values:
            return
        from marketdata.coverage.resolve import _LOOKUP_TYPES

        types = [IdentifierType.ISIN.value, *_LOOKUP_TYPES]
        stmt = (
            select(InstrumentIdentifierRow, SourceRow.name)
            .join(SourceRow, SourceRow.id == InstrumentIdentifierRow.source_id)
            .where(
                InstrumentIdentifierRow.identifier_value.in_(unique_values),
                InstrumentIdentifierRow.identifier_type.in_(types),
            )
        )
        for ident, name in self._session.execute(stmt):
            self._identifier_hits.append(
                IdentifierHit(
                    instrument_id=ident.instrument_id,
                    identifier_type=ident.identifier_type,
                    identifier_value=ident.identifier_value,
                    source_name=name,
                )
            )

    def _load_existing_instruments(self, instrument_ids: list[UUID]) -> None:
        self._instrument_ids = set()
        if not instrument_ids:
            return
        found = self._session.scalars(
            select(InstrumentRow.id).where(InstrumentRow.id.in_(instrument_ids))
        )
        self._instrument_ids = set(found)

    def _load_quotes(self, instrument_ids: list[UUID], reference_date: date) -> None:
        self._quotes = {}
        if not instrument_ids:
            return
        stmt = (
            select(InstrumentQuoteRow, SourceRow.name)
            .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
            .where(
                InstrumentQuoteRow.instrument_id.in_(instrument_ids),
                InstrumentQuoteRow.reference_date == reference_date,
            )
        )
        best_revision: dict[tuple[UUID, str, str], int] = {}
        for row, source_name in self._session.execute(stmt):
            key = (row.instrument_id, row.price_type, source_name)
            previous = best_revision.get(key)
            if previous is not None and row.revision <= previous:
                continue
            best_revision[key] = row.revision
            self._quotes[key] = StoredQuote(
                instrument_id=row.instrument_id,
                reference_date=row.reference_date,
                value=_decimal_value(row.value),
                price_type=PriceType(row.price_type),
                source_name=source_name,
                quality_status=row.quality_status,
            )

    def _load_prior_dates(self, instrument_ids: list[UUID], before: date) -> None:
        self._prior_dates = {}
        if not instrument_ids:
            return
        stmt = (
            select(
                InstrumentQuoteRow.instrument_id,
                InstrumentQuoteRow.price_type,
                SourceRow.name,
                func.max(InstrumentQuoteRow.reference_date),
            )
            .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
            .where(
                InstrumentQuoteRow.instrument_id.in_(instrument_ids),
                InstrumentQuoteRow.reference_date < before,
            )
            .group_by(
                InstrumentQuoteRow.instrument_id,
                InstrumentQuoteRow.price_type,
                SourceRow.name,
            )
        )
        for instrument_id, price_type, source_name, prior in self._session.execute(stmt):
            self._prior_dates[(instrument_id, price_type, source_name)] = prior

    def _load_ingest(self, names: list[str], reference_date: date) -> None:
        self._ingest_ok = set()
        if not names:
            return
        stmt = select(IngestionRunRow.provider).where(
            IngestionRunRow.provider.in_(names),
            IngestionRunRow.requested_reference_date == reference_date,
            IngestionRunRow.status.in_(_SUCCESSFUL_INGEST),
        )
        for provider in self._session.scalars(stmt):
            self._ingest_ok.add((provider, reference_date))

    def _load_no_public(self, instrument_ids: list[UUID], reference_date: date) -> None:
        self._no_public = set()
        if not instrument_ids:
            return
        wanted = reference_date.isoformat()
        rows = self._session.scalars(
            select(QualityEventRow.instrument_id).where(
                QualityEventRow.instrument_id.in_(instrument_ids),
                QualityEventRow.event_type == "NO_PUBLIC_PRICE",
                QualityEventRow.extra["reference_date"].as_string() == wanted,
            )
        )
        for instrument_id in rows:
            if instrument_id is not None:
                self._no_public.add((instrument_id, reference_date))

    def source(self, name: str) -> SourceView | None:
        if self._source_cache is not None:
            return self._source_cache.get(name)
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
        if self._instrument_ids is not None:
            return instrument_id in self._instrument_ids
        return self._session.get(InstrumentRow, instrument_id) is not None

    def identifiers_for(
        self,
        *,
        values: list[str],
        types: list[str],
        source_name: str | None,
    ) -> list[IdentifierHit]:
        if self._identifier_hits is not None:
            wanted_values = set(values)
            wanted_types = set(types)
            hits: list[IdentifierHit] = []
            for hit in self._identifier_hits:
                if hit.identifier_value not in wanted_values:
                    continue
                if hit.identifier_type not in wanted_types:
                    continue
                if source_name is not None and hit.source_name != source_name:
                    continue
                hits.append(hit)
            return hits
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
        if self._quotes is not None and reference_date == self._prefetch_date:
            return self._quotes.get((instrument_id, price_type.value, source_name))
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
            .limit(1)
        )
        if row is None:
            return None
        return StoredQuote(
            instrument_id=row.instrument_id,
            reference_date=row.reference_date,
            value=_decimal_value(row.value),
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
        if self._prior_dates is not None and before == self._prefetch_date:
            return self._prior_dates.get((instrument_id, price_type.value, source_name))
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
        if self._ingest_ok is not None and reference_date == self._prefetch_date:
            return (source_name, reference_date) in self._ingest_ok
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
        if self._no_public is not None and reference_date == self._prefetch_date:
            return (instrument_id, reference_date) in self._no_public
        wanted = reference_date.isoformat()
        return (
            self._session.scalar(
                select(QualityEventRow.id).where(
                    QualityEventRow.instrument_id == instrument_id,
                    QualityEventRow.event_type == "NO_PUBLIC_PRICE",
                    QualityEventRow.extra["reference_date"].as_string() == wanted,
                )
            )
            is not None
        )
