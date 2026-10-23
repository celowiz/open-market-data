from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from logging import getLogger
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
logger = getLogger(__name__)


def is_missing_sgs_values(exc: BaseException) -> bool:
    """True when python-bcb (or a test double) reports no SGS value for the window."""
    name = type(exc).__name__
    text = str(exc).lower()
    if name == "SGSError":
        return True
    return "value(s) not found" in text


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
        from bcb.exceptions import SGSError

        try:
            # Use the raw JSON instead of ``sgs.get``: when SGS answers HTTP 200 with
            # an empty list (value not published yet for the day), python-bcb 0.4.0
            # crashes in ``_format_df`` with ``KeyError: "None of ['Date'] ..."``.
            text: Any = sgs.get_json(
                int(source_series_id),
                start=start.isoformat(),
                end=end.isoformat(),
            )
        except SGSError as exc:
            logger.info(
                "bcb skip missing SGS series id=%s start=%s end=%s: %s",
                source_series_id,
                start,
                end,
                exc,
            )
            return []
        except Exception as exc:
            if not is_missing_sgs_values(exc):
                raise
            logger.info(
                "bcb skip missing SGS series id=%s start=%s end=%s: %s",
                source_series_id,
                start,
                end,
                exc,
            )
            return []
        return parse_sgs_json(text)


def parse_sgs_json(payload: str | bytes | None) -> list[tuple[date, Decimal]]:
    """Parse the SGS ``formato=json`` payload (``[{"data": "dd/mm/yyyy", "valor": "..."}]``).

    An empty list, ``null`` or an ``{"erro": ...}`` object means no values for the window.
    """
    if payload is None:
        return []
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    text = payload.strip()
    if not text:
        return []
    data = json.loads(text)
    if not isinstance(data, list):
        return []
    rows: list[tuple[date, Decimal]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_date = item.get("data")
        raw_value = item.get("valor")
        if not raw_date or raw_value is None or str(raw_value).strip() == "":
            continue
        try:
            ref = parse_sgs_date(str(raw_date))
            amount = exact_decimal(str(raw_value).strip())
        except Exception:
            continue
        rows.append((ref, amount))
    return rows
