from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from marketdata.domain.enums import PriceType
from marketdata.domain.errors import exact_decimal

SGS_SERIES = (
    ("BCB:SELIC_DAILY", "11", "Selic over", "percent_per_day"),
    ("BCB:CDI_DAILY", "12", "CDI", "percent_per_day"),
    ("BCB:SELIC_TARGET", "432", "Selic target", "percent_per_year"),
    ("BCB:PTAX_USD_SELL", "1", "PTAX USD sell", "BRL_per_USD"),
    ("BCB:PTAX_USD_BUY", "10813", "PTAX USD buy", "BRL_per_USD"),
)


@dataclass(frozen=True)
class BcbObservation:
    series_code: str
    source_series_id: str
    name: str
    unit: str
    reference_date: date
    value: Decimal
    price_type: PriceType = PriceType.REFERENCE


def parse_sgs_date(value: str) -> date:
    day, month, year = value.split("/")
    return date(int(year), int(month), int(day))


def chunk_date_range(start: date, end: date, years: int = 10) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    cursor = start
    max_span = timedelta(days=365 * years - 1)
    while cursor <= end:
        chunk_end = min(end, cursor + max_span)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


class BcbProvider:
    name = "bcb"

    def fetch_series(
        self,
        source_series_id: str,
        *,
        start: date,
        end: date,
    ) -> list[tuple[date, Decimal]]:
        from bcb import sgs

        frame: Any = sgs.get(
            {source_series_id: int(source_series_id)},
            start=start.isoformat(),
            end=end.isoformat(),
        )
        rows: list[tuple[date, Decimal]] = []
        if frame is None or getattr(frame, "empty", True):
            return rows
        column = frame.columns[0]
        for index, value in frame[column].items():
            if value is None:
                continue
            try:
                amount = exact_decimal(str(value))
            except Exception:
                continue
            ref = index.date() if hasattr(index, "date") else date.fromisoformat(str(index)[:10])
            rows.append((ref, amount))
        return rows
