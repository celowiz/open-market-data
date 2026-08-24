from datetime import date
from decimal import Decimal
from pathlib import Path

from marketdata.providers.bcb import chunk_date_range
from marketdata.providers.tesouro import map_title_type, parse_tesouro_csv, tesouro_instrument_key

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tesouro" / "sample.csv"


def test_parse_tesouro_csv() -> None:
    records = parse_tesouro_csv(
        FIXTURE.read_text(encoding="utf-8"), reference_date=date(2026, 8, 21)
    )
    assert records
    assert map_title_type("Tesouro Prefixado") == "LTN"
    pu_base = next(item for item in records if item.source_field == "PU Base Manha")
    assert pu_base.value == Decimal("731.09")
    assert tesouro_instrument_key(pu_base.title_type, pu_base.maturity_date) == "LTN:2029-01-01"


def test_chunk_date_range_respects_ten_years() -> None:
    chunks = chunk_date_range(date(2000, 1, 1), date(2026, 1, 1), years=10)
    assert chunks[0][0] == date(2000, 1, 1)
    assert (chunks[0][1] - chunks[0][0]).days <= 3650
    assert chunks[-1][1] == date(2026, 1, 1)
