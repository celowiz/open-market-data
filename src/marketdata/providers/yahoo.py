from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from marketdata.domain.enums import PriceType
from marketdata.domain.errors import exact_decimal


@dataclass(frozen=True)
class YahooQuoteRecord:
    symbol: str
    reference_date: date
    value: Decimal
    currency: str | None
    price_type: PriceType = PriceType.CLOSE
    source_field: str = "Close"


def _is_missing_close(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.lower() in {"nan", "none", "<na>", "nat"}


def _row_date(row: Mapping[str, object]) -> date | None:
    raw = row.get("date", row.get("Date"))
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    date_fn = getattr(raw, "date", None)
    if callable(date_fn):
        parsed = date_fn()
        if isinstance(parsed, date):
            return parsed
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def parse_yahoo_history(
    symbol: str,
    rows: Iterable[Mapping[str, object]],
    *,
    currency: str | None = None,
) -> list[YahooQuoteRecord]:
    records: list[YahooQuoteRecord] = []
    for row in rows:
        reference = _row_date(row)
        if reference is None:
            continue
        close = _column_value(row, "Close")
        if not _is_missing_close(close):
            try:
                value = exact_decimal(str(close).strip())
            except Exception:
                pass
            else:
                records.append(
                    YahooQuoteRecord(
                        symbol=symbol,
                        reference_date=reference,
                        value=value,
                        currency=currency,
                        price_type=PriceType.CLOSE,
                        source_field="Close",
                    )
                )
        adj = _column_value(row, "Adj Close", "AdjClose")
        if not _is_missing_close(adj):
            try:
                adj_value = exact_decimal(str(adj).strip())
            except Exception:
                continue
            records.append(
                YahooQuoteRecord(
                    symbol=symbol,
                    reference_date=reference,
                    value=adj_value,
                    currency=currency,
                    price_type=PriceType.ADJUSTED_CLOSE,
                    source_field="Adj Close",
                )
            )
    return records


def _column_value(row: Mapping[str, object], *names: str) -> object:
    lowered = {name.lower() for name in names}
    for name in names:
        if name in row:
            return row[name]
    for key, value in row.items():
        if str(key).strip().lower() in lowered:
            return value
    return None


def _frame_to_row_maps(frame: Any) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if frame is None or getattr(frame, "empty", True):
        return rows
    for index, series in frame.iterrows():
        item: dict[str, object] = {}
        date_fn = getattr(index, "date", None)
        if callable(date_fn):
            item["date"] = date_fn()
        else:
            item["date"] = date.fromisoformat(str(index)[:10])
        for column in series.index:
            label = column[0] if isinstance(column, tuple) else column
            item[str(label)] = series[column]
        rows.append(item)
    return rows


class YahooProvider:
    name = "yahoo"

    def fetch_history(self, symbol: str, *, start: date, end: date) -> list[YahooQuoteRecord]:
        import yfinance as yf

        frame: Any = yf.Ticker(symbol).history(
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=False,
            actions=False,
        )
        return parse_yahoo_history(symbol, _frame_to_row_maps(frame))
