from datetime import date
from decimal import Decimal
from pathlib import Path

from marketdata.domain.enums import PriceType
from marketdata.providers.yahoo import parse_yahoo_history

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "marketdata"
ALLOWED_YFINANCE = SRC_ROOT / "providers" / "yahoo.py"


def test_parse_yahoo_history_uses_close_not_adj_close() -> None:
    records = parse_yahoo_history(
        "AAPL",
        [
            {
                "date": date(2026, 8, 21),
                "Close": "185.64",
                "Adj Close": "180.00",
                "Open": "184.00",
                "Volume": "1000",
            }
        ],
        currency="USD",
    )
    closes = [row for row in records if row.price_type is PriceType.CLOSE]
    adjusted = [row for row in records if row.price_type is PriceType.ADJUSTED_CLOSE]
    assert len(closes) == 1
    record = closes[0]
    assert record.symbol == "AAPL"
    assert record.reference_date == date(2026, 8, 21)
    assert record.value == Decimal("185.64")
    assert record.value != Decimal("180.00")
    assert record.price_type is PriceType.CLOSE
    assert record.source_field == "Close"
    assert record.currency == "USD"
    assert len(adjusted) == 1
    assert adjusted[0].value == Decimal("180.00")
    assert adjusted[0].source_field == "Adj Close"
    assert adjusted[0].price_type is PriceType.ADJUSTED_CLOSE


def test_parse_yahoo_history_skips_missing_close() -> None:
    records = parse_yahoo_history(
        "AAPL",
        [
            {"date": date(2026, 8, 24), "Close": "nan"},
        ],
    )
    assert [row.price_type for row in records] == []


def test_parse_yahoo_history_adj_close_is_yahoo_column_not_recomputed() -> None:
    records = parse_yahoo_history(
        "PETR4.SA",
        [
            {
                "date": date(2026, 8, 21),
                "Close": "42.11",
                "Adj Close": "40.00",
                "Dividends": "1.50",
                "Stock Splits": "0.0",
            }
        ],
    )
    adjusted = next(row for row in records if row.price_type is PriceType.ADJUSTED_CLOSE)
    assert adjusted.value == Decimal("40.00")
    assert adjusted.value != Decimal("42.11")
    assert adjusted.source_field == "Adj Close"


def test_yfinance_is_isolated_to_yahoo_provider() -> None:
    offenders: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        if path.resolve() == ALLOWED_YFINANCE.resolve():
            continue
        if "yfinance" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(SRC_ROOT)).replace("\\", "/"))
    assert offenders == []
