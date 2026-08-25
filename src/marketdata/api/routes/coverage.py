from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from marketdata.api.deps import get_db
from marketdata.config import get_settings
from marketdata.coverage.csv import load_universe
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


def get_coverage_config_dir() -> Path:
    return get_settings().coverage_config_dir


@router.get("/coverage", response_model=CoverageResponse)
def coverage(
    date_filter: date = Query(..., alias="date"),
    universe: Literal["example", "operator"] = Query(default="example"),
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
