from uuid import UUID

from marketdata.coverage.csv import UniverseRow
from marketdata.coverage.store import CoverageStore, IdentifierHit
from marketdata.domain.enums import IdentifierType

_LOOKUP_TYPES = (
    IdentifierType.TICKER.value,
    IdentifierType.YAHOO_SYMBOL.value,
    IdentifierType.SOURCE_ID.value,
    IdentifierType.B3_SECURITY_ID.value,
)


def _unique_ids(hits: list[IdentifierHit]) -> list[UUID]:
    seen: dict[UUID, None] = {}
    for hit in hits:
        seen.setdefault(hit.instrument_id, None)
    return list(seen)


def resolve_row(row: UniverseRow, store: CoverageStore) -> list[UUID]:
    if row.instrument_id is not None:
        return [row.instrument_id] if store.instrument_exists(row.instrument_id) else []
    source_name = row.preferred_provider or None
    if row.isin:
        isin_ids = _unique_ids(
            store.identifiers_for(
                values=[row.isin],
                types=[IdentifierType.ISIN.value],
                source_name=source_name,
            )
        )
        if isin_ids:
            return isin_ids
    ticker = row.ticker.strip()
    if not ticker:
        return []
    return _unique_ids(
        store.identifiers_for(
            values=[ticker],
            types=list(_LOOKUP_TYPES),
            source_name=source_name,
        )
    )
