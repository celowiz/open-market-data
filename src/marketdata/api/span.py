from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from marketdata.coverage.csv import UniverseRow
from marketdata.domain.enums import IdentifierType
from marketdata.storage.models import (
    InstrumentIdentifierRow,
    InstrumentQuoteRow,
    InstrumentRow,
    SourceRow,
)

_LOOKUP_TYPES = (
    IdentifierType.TICKER.value,
    IdentifierType.YAHOO_SYMBOL.value,
    IdentifierType.SOURCE_ID.value,
    IdentifierType.B3_SECURITY_ID.value,
)
_SPAN_IDENTIFIER_TYPES = (*_LOOKUP_TYPES, IdentifierType.ISIN.value)


@dataclass(frozen=True)
class QuoteSpan:
    min_date: date
    max_date: date
    quote_count: int


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def load_instrument_spans(
    session: Session,
    instrument_ids: Sequence[UUID],
    *,
    source_name: str | None = None,
) -> dict[UUID, QuoteSpan]:
    ids = list(instrument_ids)
    if not ids:
        return {}
    stmt = (
        select(
            InstrumentQuoteRow.instrument_id,
            func.min(InstrumentQuoteRow.reference_date),
            func.max(InstrumentQuoteRow.reference_date),
            func.count(func.distinct(InstrumentQuoteRow.reference_date)),
        )
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .where(
            InstrumentQuoteRow.instrument_id.in_(ids),
            SourceRow.public_api_enabled.is_(True),
        )
        .group_by(InstrumentQuoteRow.instrument_id)
    )
    filtered = _optional_text(source_name)
    if filtered is not None:
        stmt = stmt.where(SourceRow.name == filtered)
    result: dict[UUID, QuoteSpan] = {}
    for instrument_id, min_date, max_date, quote_count in session.execute(stmt):
        result[instrument_id] = QuoteSpan(
            min_date=min_date,
            max_date=max_date,
            quote_count=int(quote_count),
        )
    return result


def load_instrument_source_spans(
    session: Session,
    instrument_ids: Sequence[UUID],
    *,
    source_name: str | None = None,
) -> dict[tuple[UUID, str], QuoteSpan]:
    ids = list(instrument_ids)
    if not ids:
        return {}
    stmt = (
        select(
            InstrumentQuoteRow.instrument_id,
            SourceRow.name,
            func.min(InstrumentQuoteRow.reference_date),
            func.max(InstrumentQuoteRow.reference_date),
            func.count(func.distinct(InstrumentQuoteRow.reference_date)),
        )
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .where(
            InstrumentQuoteRow.instrument_id.in_(ids),
            SourceRow.public_api_enabled.is_(True),
        )
        .group_by(InstrumentQuoteRow.instrument_id, SourceRow.name)
    )
    filtered = _optional_text(source_name)
    if filtered is not None:
        stmt = stmt.where(SourceRow.name == filtered)
    result: dict[tuple[UUID, str], QuoteSpan] = {}
    for instrument_id, name, min_date, max_date, quote_count in session.execute(stmt):
        result[(instrument_id, name)] = QuoteSpan(
            min_date=min_date,
            max_date=max_date,
            quote_count=int(quote_count),
        )
    return result


def resolve_universe_instrument_ids(
    session: Session,
    rows: Sequence[UniverseRow],
    *,
    source_name: str | None = None,
) -> list[UUID | None]:
    csv_ids = [row.instrument_id for row in rows if row.instrument_id is not None]
    existing: set[UUID] = set()
    if csv_ids:
        existing = set(
            session.scalars(select(InstrumentRow.id).where(InstrumentRow.id.in_(csv_ids)))
        )

    values = {row.ticker.strip() for row in rows if row.ticker.strip()}
    values.update(row.isin for row in rows if row.isin)
    hits: dict[tuple[str, str, str], list[UUID]] = {}
    if values:
        stmt = (
            select(
                InstrumentIdentifierRow.identifier_value,
                InstrumentIdentifierRow.identifier_type,
                InstrumentIdentifierRow.instrument_id,
                SourceRow.name,
            )
            .join(SourceRow, SourceRow.id == InstrumentIdentifierRow.source_id)
            .where(
                InstrumentIdentifierRow.identifier_value.in_(values),
                InstrumentIdentifierRow.identifier_type.in_(_SPAN_IDENTIFIER_TYPES),
            )
        )
        filtered = _optional_text(source_name)
        if filtered is not None:
            stmt = stmt.where(SourceRow.name == filtered)
        for value, identifier_type, instrument_id, name in session.execute(stmt):
            hits.setdefault((value, identifier_type, name), []).append(instrument_id)

    resolved: list[UUID | None] = []
    for row in rows:
        resolved.append(
            _resolve_row(
                row,
                existing=existing,
                hits=hits,
                source_name=_optional_text(source_name),
            )
        )
    return resolved


def _unique_ids(ids: list[UUID]) -> list[UUID]:
    seen: dict[UUID, None] = {}
    for instrument_id in ids:
        seen.setdefault(instrument_id, None)
    return list(seen)


def _ids_for(
    hits: dict[tuple[str, str, str], list[UUID]],
    *,
    value: str,
    types: Sequence[str],
    source_name: str | None,
) -> list[UUID]:
    matched: list[UUID] = []
    for identifier_type in types:
        if source_name is None:
            for (hit_value, hit_type, _), instrument_ids in hits.items():
                if hit_value == value and hit_type == identifier_type:
                    matched.extend(instrument_ids)
            continue
        matched.extend(hits.get((value, identifier_type, source_name), []))
    return _unique_ids(matched)


def _resolve_row(
    row: UniverseRow,
    *,
    existing: set[UUID],
    hits: dict[tuple[str, str, str], list[UUID]],
    source_name: str | None,
) -> UUID | None:
    if row.instrument_id is not None:
        return row.instrument_id if row.instrument_id in existing else None
    source = source_name or (row.preferred_provider or None) or None
    if row.isin:
        isin_ids = _ids_for(
            hits,
            value=row.isin,
            types=[IdentifierType.ISIN.value],
            source_name=source,
        )
        if isin_ids:
            return isin_ids[0] if len(isin_ids) == 1 else None
    ticker = row.ticker.strip()
    if not ticker:
        return None
    ticker_ids = _ids_for(
        hits,
        value=ticker,
        types=_LOOKUP_TYPES,
        source_name=source,
    )
    return ticker_ids[0] if len(ticker_ids) == 1 else None
