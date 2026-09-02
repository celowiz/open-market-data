from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from marketdata.api.access import source_row_allows_public_api
from marketdata.api.deps import get_db
from marketdata.ingestion.config_tables import load_fred_series
from marketdata.storage.models import InstrumentIdentifierRow, InstrumentRow, MarketSeriesRow, SourceRow

router = APIRouter()


class MacroSeriesItem(BaseModel):
    code: str
    name: str
    source: str
    kind: str
    unit: str | None = None
    identifier: str | None = None


class MacroSeriesResponse(BaseModel):
    series: list[MacroSeriesItem]


@router.get("/macro", response_model=MacroSeriesResponse)
def list_macro(session: Session = Depends(get_db)) -> MacroSeriesResponse:
    items: list[MacroSeriesItem] = []
    seen: set[str] = set()
    for spec in load_fred_series():
        items.append(
            MacroSeriesItem(
                code=spec.code,
                name=spec.name,
                source="fred",
                kind="instrument",
                unit=spec.unit,
                identifier=spec.series_id,
            )
        )
        seen.add(spec.code)
    series_rows = session.execute(
        select(MarketSeriesRow, SourceRow)
        .join(SourceRow, SourceRow.id == MarketSeriesRow.source_id)
        .where(SourceRow.name.in_(("ibge", "fred", "bcb")))
        .order_by(MarketSeriesRow.code.asc())
    ).all()
    for series, source in series_rows:
        if not source_row_allows_public_api(source):
            continue
        if series.code in seen:
            continue
        items.append(
            MacroSeriesItem(
                code=series.code,
                name=series.name,
                source=source.name,
                kind="series",
                unit=series.unit,
                identifier=series.source_series_id,
            )
        )
        seen.add(series.code)
    fred_source = session.scalar(select(SourceRow).where(SourceRow.name == "fred"))
    if fred_source is not None and source_row_allows_public_api(fred_source):
        quoted = session.execute(
            select(InstrumentRow, InstrumentIdentifierRow)
            .join(
                InstrumentIdentifierRow,
                InstrumentIdentifierRow.instrument_id == InstrumentRow.id,
            )
            .where(
                InstrumentIdentifierRow.source_id == fred_source.id,
                InstrumentIdentifierRow.identifier_type == "TICKER",
            )
        ).all()
        for instrument, ident in quoted:
            code = f"FRED:{ident.identifier_value}"
            if code in seen or ident.identifier_value in seen:
                continue
            items.append(
                MacroSeriesItem(
                    code=code,
                    name=instrument.name,
                    source="fred",
                    kind="instrument",
                    unit=instrument.extra.get("unit") if isinstance(instrument.extra, dict) else None,
                    identifier=ident.identifier_value,
                )
            )
    return MacroSeriesResponse(series=items)
