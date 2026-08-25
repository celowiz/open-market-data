from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import polars as pl
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from marketdata.datasets.access import PUBLIC_DATASET_POLICY_VALUES
from marketdata.datasets.attribution import attribution_for_source
from marketdata.datasets.schema import (
    INSTRUMENTS_SCHEMA,
    QUOTES_SCHEMA,
    RATES_SCHEMA,
    SCHEMA_VERSION,
    SOURCES_SCHEMA,
    frame_from_records,
)
from marketdata.domain.enums import IdentifierType, PriceType
from marketdata.domain.errors import exact_decimal
from marketdata.storage.models import (
    InstrumentIdentifierRow,
    InstrumentQuoteRow,
    InstrumentRow,
    MarketSeriesObservationRow,
    MarketSeriesRow,
    SourceRow,
)

_IDENTIFIER_COLUMNS = {
    IdentifierType.TICKER.value: "ticker",
    IdentifierType.ISIN.value: "isin",
    IdentifierType.CNPJ_FUNDO_CLASSE.value: "cnpj_fundo_classe",
    IdentifierType.CVM_SUBCLASS_ID.value: "cvm_subclass_id",
    IdentifierType.TITLE_TYPE.value: "title_type",
}


def _uuid_str(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _dataset_source_filter():
    return (
        SourceRow.public_dataset_enabled.is_(True),
        SourceRow.redistribution_policy.in_(PUBLIC_DATASET_POLICY_VALUES),
    )


def _latest_quote_subquery():
    return (
        select(
            InstrumentQuoteRow.instrument_id,
            InstrumentQuoteRow.reference_date,
            InstrumentQuoteRow.source_id,
            InstrumentQuoteRow.price_type,
            func.max(InstrumentQuoteRow.revision).label("revision"),
        )
        .group_by(
            InstrumentQuoteRow.instrument_id,
            InstrumentQuoteRow.reference_date,
            InstrumentQuoteRow.source_id,
            InstrumentQuoteRow.price_type,
        )
        .subquery()
    )


def _latest_observation_subquery():
    return (
        select(
            MarketSeriesObservationRow.series_id,
            MarketSeriesObservationRow.reference_date,
            MarketSeriesObservationRow.source_id,
            func.max(MarketSeriesObservationRow.revision).label("revision"),
        )
        .group_by(
            MarketSeriesObservationRow.series_id,
            MarketSeriesObservationRow.reference_date,
            MarketSeriesObservationRow.source_id,
        )
        .subquery()
    )


def _pivot_identifiers(
    rows: list[InstrumentIdentifierRow], *, preferred_source_id: UUID | None
) -> dict[str, str | None]:
    by_type: dict[str, list[InstrumentIdentifierRow]] = defaultdict(list)
    for row in rows:
        column = _IDENTIFIER_COLUMNS.get(row.identifier_type)
        if column is None:
            continue
        by_type[column].append(row)

    pivoted: dict[str, str | None] = {column: None for column in _IDENTIFIER_COLUMNS.values()}
    for column, candidates in by_type.items():
        preferred = [
            item
            for item in candidates
            if preferred_source_id and item.source_id == preferred_source_id
        ]
        chosen = preferred[0] if preferred else candidates[0]
        pivoted[column] = chosen.identifier_value
    return pivoted


def _identifiers_by_instrument(
    session: Session, instrument_ids: list[UUID]
) -> dict[UUID, list[InstrumentIdentifierRow]]:
    grouped: dict[UUID, list[InstrumentIdentifierRow]] = defaultdict(list)
    if not instrument_ids:
        return grouped
    rows = session.scalars(
        select(InstrumentIdentifierRow).where(
            InstrumentIdentifierRow.instrument_id.in_(instrument_ids)
        )
    ).all()
    for row in rows:
        grouped[row.instrument_id].append(row)
    return grouped


def extract_sources(session: Session) -> pl.DataFrame:
    rows = session.scalars(
        select(SourceRow).where(*_dataset_source_filter()).order_by(SourceRow.name)
    ).all()
    records: list[dict[str, object]] = []
    for row in rows:
        records.append(
            {
                "name": row.name,
                "display_name": row.display_name,
                "official": row.official,
                "data_license": row.data_license,
                "redistribution_policy": row.redistribution_policy,
                "homepage": row.homepage,
                "documentation_url": row.documentation_url,
                "attribution": attribution_for_source(row.name),
            }
        )
    return frame_from_records(records, SOURCES_SCHEMA)


def extract_quotes(session: Session, *, price_type: str | None = None) -> pl.DataFrame:
    latest = _latest_quote_subquery()
    stmt = (
        select(InstrumentQuoteRow, SourceRow, InstrumentRow.maturity_date)
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .join(InstrumentRow, InstrumentRow.id == InstrumentQuoteRow.instrument_id)
        .join(
            latest,
            and_(
                InstrumentQuoteRow.instrument_id == latest.c.instrument_id,
                InstrumentQuoteRow.reference_date == latest.c.reference_date,
                InstrumentQuoteRow.source_id == latest.c.source_id,
                InstrumentQuoteRow.price_type == latest.c.price_type,
                InstrumentQuoteRow.revision == latest.c.revision,
            ),
        )
        .where(*_dataset_source_filter())
    )
    if price_type is not None:
        stmt = stmt.where(InstrumentQuoteRow.price_type == price_type)
    stmt = stmt.order_by(
        SourceRow.name,
        InstrumentQuoteRow.reference_date,
        InstrumentQuoteRow.instrument_id,
        InstrumentQuoteRow.price_type,
    )
    fetched = session.execute(stmt).all()
    instrument_ids = [quote.instrument_id for quote, _source, _maturity in fetched]
    identifiers = _identifiers_by_instrument(session, instrument_ids)
    records: list[dict[str, object]] = []
    for quote, source, maturity in fetched:
        helpers = _pivot_identifiers(
            identifiers.get(quote.instrument_id, []),
            preferred_source_id=quote.source_id,
        )
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "instrument_id": str(quote.instrument_id),
                "source": source.name,
                "reference_date": quote.reference_date,
                "value": exact_decimal(Decimal(quote.value)),
                "currency": quote.currency,
                "unit": quote.unit,
                "price_type": quote.price_type,
                "is_official": quote.is_official,
                "retrieved_at": _as_utc(quote.retrieved_at),
                "raw_artifact_id": _uuid_str(quote.raw_artifact_id),
                "ingestion_run_id": _uuid_str(quote.ingestion_run_id),
                "revision": quote.revision,
                "quality_status": quote.quality_status,
                "ticker": helpers["ticker"],
                "isin": helpers["isin"],
                "cnpj_fundo_classe": helpers["cnpj_fundo_classe"],
                "cvm_subclass_id": helpers["cvm_subclass_id"],
                "title_type": helpers["title_type"],
                "maturity_date": maturity,
            }
        )
    return frame_from_records(records, QUOTES_SCHEMA)


def extract_fund_nav(session: Session) -> pl.DataFrame:
    return extract_quotes(session, price_type=PriceType.FUND_NAV.value)


def extract_instruments(session: Session) -> pl.DataFrame:
    quote_rows = session.execute(
        select(InstrumentQuoteRow.instrument_id, SourceRow.id, SourceRow.name)
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .where(*_dataset_source_filter())
        .distinct()
    ).all()
    if not quote_rows:
        return frame_from_records([], INSTRUMENTS_SCHEMA)

    source_by_instrument: dict[UUID, str] = {}
    source_id_by_instrument: dict[UUID, UUID] = {}
    for instrument_id, source_id, source_name in quote_rows:
        current = source_by_instrument.get(instrument_id)
        if current is None or source_name < current:
            source_by_instrument[instrument_id] = source_name
            source_id_by_instrument[instrument_id] = source_id

    instrument_ids = list(source_by_instrument)
    instruments = session.scalars(
        select(InstrumentRow)
        .where(InstrumentRow.id.in_(instrument_ids))
        .order_by(InstrumentRow.name, InstrumentRow.id)
    ).all()
    identifiers = _identifiers_by_instrument(session, instrument_ids)
    records: list[dict[str, object]] = []
    for instrument in instruments:
        helpers = _pivot_identifiers(
            identifiers.get(instrument.id, []),
            preferred_source_id=source_id_by_instrument.get(instrument.id),
        )
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "instrument_id": str(instrument.id),
                "source": source_by_instrument[instrument.id],
                "asset_class": instrument.asset_class,
                "instrument_type": instrument.instrument_type,
                "name": instrument.name,
                "currency": instrument.currency,
                "exchange": instrument.exchange,
                "mic": instrument.mic,
                "issuer": instrument.issuer,
                "maturity_date": instrument.maturity_date,
                "active_from": instrument.active_from,
                "active_until": instrument.active_until,
                "ticker": helpers["ticker"],
                "isin": helpers["isin"],
                "cnpj_fundo_classe": helpers["cnpj_fundo_classe"],
                "cvm_subclass_id": helpers["cvm_subclass_id"],
                "title_type": helpers["title_type"],
            }
        )
    return frame_from_records(records, INSTRUMENTS_SCHEMA)


def extract_rates(session: Session) -> pl.DataFrame:
    latest = _latest_observation_subquery()
    stmt = (
        select(MarketSeriesObservationRow, MarketSeriesRow, SourceRow)
        .join(MarketSeriesRow, MarketSeriesRow.id == MarketSeriesObservationRow.series_id)
        .join(SourceRow, SourceRow.id == MarketSeriesObservationRow.source_id)
        .join(
            latest,
            and_(
                MarketSeriesObservationRow.series_id == latest.c.series_id,
                MarketSeriesObservationRow.reference_date == latest.c.reference_date,
                MarketSeriesObservationRow.source_id == latest.c.source_id,
                MarketSeriesObservationRow.revision == latest.c.revision,
            ),
        )
        .where(*_dataset_source_filter())
        .order_by(
            SourceRow.name,
            MarketSeriesRow.code,
            MarketSeriesObservationRow.reference_date,
        )
    )
    records: list[dict[str, object]] = []
    for observation, series, source in session.execute(stmt).all():
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "series_code": series.code,
                "source_series_id": series.source_series_id,
                "source": source.name,
                "name": series.name,
                "reference_date": observation.reference_date,
                "value": exact_decimal(Decimal(observation.value)),
                "unit": series.unit,
                "value_semantics": series.value_semantics,
                "retrieved_at": _as_utc(observation.retrieved_at),
                "raw_artifact_id": _uuid_str(observation.raw_artifact_id),
                "ingestion_run_id": _uuid_str(observation.ingestion_run_id),
                "revision": observation.revision,
                "quality_status": observation.quality_status,
            }
        )
    return frame_from_records(records, RATES_SCHEMA)


EXTRACTORS = {
    "sources": extract_sources,
    "instruments": extract_instruments,
    "quotes": extract_quotes,
    "fund_nav": extract_fund_nav,
    "rates": extract_rates,
}
