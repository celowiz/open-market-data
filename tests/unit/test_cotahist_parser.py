from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from marketdata.domain.enums import PriceType
from marketdata.providers.cotahist import (
    cotahist_year_url,
    parse_cotahist,
    parse_cotahist_zip,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "b3"


def test_cotahist_year_url_http_and_https() -> None:
    http_url = cotahist_year_url(2020)
    https_url = cotahist_year_url(2020, https=True)
    assert http_url.startswith("http://")
    assert https_url.startswith("https://")
    assert "InstDados/SerHist/COTAHIST_A2020.ZIP" in http_url
    assert "InstDados/SerHist/COTAHIST_A2020.ZIP" in https_url


def test_cotahist_preult_parses_to_decimal_not_float() -> None:
    text = (FIXTURES / "cotahist_sample.txt").read_text(encoding="latin-1")
    records = parse_cotahist(text)
    assert len(records) == 1
    petr4 = records[0]
    assert petr4.ticker == "PETR4"
    assert petr4.reference_date == date(2026, 8, 21)
    assert petr4.last_price == Decimal("36.50")
    assert type(petr4.last_price) is Decimal
    assert not isinstance(petr4.last_price, float)
    assert petr4.currency == "BRL"
    assert petr4.price_type is PriceType.LAST
    assert petr4.extra.get("origin") == "COTAHIST"
    assert petr4.extra.get("source_field") == "PREULT"


def test_cotahist_does_not_emit_official_settlement() -> None:
    text = (FIXTURES / "cotahist_sample.txt").read_text(encoding="latin-1")
    records = parse_cotahist(text)
    assert records
    assert all(record.price_type is PriceType.LAST for record in records)
    assert all(record.price_type is not PriceType.OFFICIAL_SETTLEMENT for record in records)


def test_cotahist_skips_header_and_trailer() -> None:
    text = (FIXTURES / "cotahist_sample.txt").read_text(encoding="latin-1")
    records = parse_cotahist(text)
    assert all(record.ticker != "COTAHIST.2026" for record in records)


def test_cotahist_indopc_does_not_change_price_type() -> None:
    text = (FIXTURES / "cotahist_sample.txt").read_text(encoding="latin-1")
    quote_line = next(line for line in text.splitlines() if line.startswith("01"))
    corrected = quote_line[:201] + "1" + quote_line[202:]
    records = parse_cotahist("\n".join(["00", corrected, "99"]))
    assert len(records) == 1
    assert records[0].price_type is PriceType.LAST
    assert records[0].last_price == Decimal("36.50")
    assert records[0].extra.get("INDOPC") == "1"


def test_parse_cotahist_zip_reads_inner_text() -> None:
    text = (FIXTURES / "cotahist_sample.txt").read_bytes()
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("COTAHIST_A2026.TXT", text)
    records = parse_cotahist_zip(buffer.getvalue())
    assert len(records) == 1
    assert records[0].last_price == Decimal("36.50")
