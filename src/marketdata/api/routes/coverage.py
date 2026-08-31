from datetime import date
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from marketdata.api.deps import get_db
from marketdata.api.span import (
    QuoteSpan,
    load_instrument_source_spans,
    resolve_universe_instrument_ids,
)
from marketdata.config import get_settings
from marketdata.coverage.csv import UniverseRow, load_universe
from marketdata.coverage.engine import CoverageMode, evaluate_coverage
from marketdata.coverage.paths import named_universe_path
from marketdata.coverage.store import SessionCoverageStore
from marketdata.domain.errors import decimal_json

router = APIRouter()


class CoverageItemResponse(BaseModel):
    instrument: str
    asset_class: str
    provider: str | None
    reference_date: date
    price: str | None
    price_type: str | None
    status: str
    staleness: int | None
    missing_reason: str | None


class CoverageResponse(BaseModel):
    date: date
    universe: str
    mode: str
    universe_size: int
    priced: int
    priced_pct: str
    missing_reason_counts: dict[str, int]
    results: list[CoverageItemResponse]
    next_cursor: int | None = None


class CoverageSpanItem(BaseModel):
    ticker: str
    instrument_id: str | None = None
    source: str | None = None
    min_date: date | None = None
    max_date: date | None = None
    quote_count: int = 0


class CoverageSpanResponse(BaseModel):
    universe: str
    universe_size: int
    instruments_with_quotes: int
    min_date: date | None = None
    max_date: date | None = None
    quote_count: int = 0
    source: str | None = None
    results: list[CoverageSpanItem]


def get_coverage_config_dir() -> Path:
    return get_settings().coverage_config_dir


@router.get("/coverage", response_model=CoverageResponse)
def coverage(
    date_filter: date = Query(..., alias="date"),
    universe: Literal["example", "operator", "scratch"] = Query(default="example"),
    limit: int = Query(default=100, ge=1, le=1000),
    cursor: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
    config_dir: Path = Depends(get_coverage_config_dir),
) -> CoverageResponse:
    csv_path = named_universe_path(universe, base=config_dir)
    if not csv_path.is_file():
        raise HTTPException(status_code=404, detail="universe not found")
    report = evaluate_coverage(
        load_universe(csv_path),
        reference_date=date_filter,
        store=SessionCoverageStore(session),
        mode=CoverageMode.PUBLIC,
        universe_name=universe,
    )
    page = report.results[cursor : cursor + limit]
    next_cursor = cursor + limit if cursor + limit < len(report.results) else None
    return CoverageResponse(
        date=report.date,
        universe=report.universe,
        mode=report.mode.value,
        universe_size=report.universe_size,
        priced=report.priced,
        priced_pct=decimal_json(report.priced_pct),
        missing_reason_counts=report.missing_reason_counts,
        results=[
            CoverageItemResponse(
                instrument=item.instrument,
                asset_class=item.asset_class,
                provider=item.provider,
                reference_date=item.reference_date,
                price=decimal_json(item.price) if item.price is not None else None,
                price_type=item.price_type,
                status=item.status.value,
                staleness=item.staleness,
                missing_reason=item.missing_reason.value if item.missing_reason else None,
            )
            for item in page
        ],
        next_cursor=next_cursor,
    )


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _span_source(row: UniverseRow, source_name: str | None) -> str | None:
    return source_name or (row.preferred_provider or None) or None


def _span_for_row(
    *,
    instrument_id: UUID | None,
    source: str | None,
    spans: dict[tuple[UUID, str], QuoteSpan],
) -> QuoteSpan | None:
    if instrument_id is None:
        return None
    if source is not None:
        return spans.get((instrument_id, source))
    matching = [item for (iid, _), item in spans.items() if iid == instrument_id]
    if not matching:
        return None
    return QuoteSpan(
        min_date=min(item.min_date for item in matching),
        max_date=max(item.max_date for item in matching),
        quote_count=sum(item.quote_count for item in matching),
    )


@router.get("/coverage/span", response_model=CoverageSpanResponse)
def coverage_span(
    universe: Literal["example", "operator", "scratch"] = Query(default="example"),
    source: str | None = Query(default=None),
    session: Session = Depends(get_db),
    config_dir: Path = Depends(get_coverage_config_dir),
) -> CoverageSpanResponse:
    csv_path = named_universe_path(universe, base=config_dir)
    if not csv_path.is_file():
        raise HTTPException(status_code=404, detail="universe not found")
    rows = load_universe(csv_path)
    source_name = _optional_text(source)
    resolved = resolve_universe_instrument_ids(session, rows, source_name=source_name)
    instrument_ids = [instrument_id for instrument_id in resolved if instrument_id is not None]
    spans = load_instrument_source_spans(session, instrument_ids, source_name=source_name)
    results: list[CoverageSpanItem] = []
    for row, instrument_id in zip(rows, resolved, strict=True):
        item_source = _span_source(row, source_name)
        span = _span_for_row(instrument_id=instrument_id, source=item_source, spans=spans)
        results.append(
            CoverageSpanItem(
                ticker=row.ticker,
                instrument_id=str(instrument_id) if instrument_id is not None else None,
                source=item_source,
                min_date=span.min_date if span is not None else None,
                max_date=span.max_date if span is not None else None,
                quote_count=span.quote_count if span is not None else 0,
            )
        )
    min_dates = [item.min_date for item in results if item.min_date is not None]
    max_dates = [item.max_date for item in results if item.max_date is not None]
    return CoverageSpanResponse(
        universe=universe,
        universe_size=len(results),
        instruments_with_quotes=sum(1 for item in results if item.quote_count > 0),
        min_date=min(min_dates) if min_dates else None,
        max_date=max(max_dates) if max_dates else None,
        quote_count=sum(item.quote_count for item in results),
        source=source_name,
        results=results,
    )
