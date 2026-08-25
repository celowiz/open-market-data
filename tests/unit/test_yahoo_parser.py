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
    assert len(records) == 1
    record = records[0]
    assert record.symbol == "AAPL"
    assert record.reference_date == date(2026, 8, 21)
    assert record.value == Decimal("185.64")
    assert record.value != Decimal("180.00")
    assert record.price_type is PriceType.CLOSE
    assert record.source_field == "Close"
    assert record.currency == "USD"


def test_parse_yahoo_history_skips_missing_close() -> None:
    records = parse_yahoo_history(
        "AAPL",
        [
            {"date": date(2026, 8, 22), "Adj Close": "180.00"},
            {"date": date(2026, 8, 23), "Close": None, "Adj Close": "181.00"},
            {"date": date(2026, 8, 24), "Close": "nan"},
        ],
    )
    assert records == []


def test_yfinance_is_isolated_to_yahoo_provider() -> None:
    offenders: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        if path.resolve() == ALLOWED_YFINANCE.resolve():
            continue
        if "yfinance" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(SRC_ROOT)).replace("\\", "/"))
    assert offenders == []
