from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from marketdata.providers.b3 import (
    B3ParseError,
    parse_instrument_master,
    parse_price_report,
    pregao_filelist,
    validate_b3_zip,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "b3"


def _nested_zip(outer_name: str, inner_name: str, xml: bytes) -> bytes:
    inner_buffer = BytesIO()
    with ZipFile(inner_buffer, "w") as inner:
        inner.writestr(inner_name, xml)
    outer_buffer = BytesIO()
    with ZipFile(outer_buffer, "w") as outer:
        outer.writestr(outer_name, inner_buffer.getvalue())
    return outer_buffer.getvalue()


def test_pregao_filelist_uses_spre_for_equities() -> None:
    assert pregao_filelist("186", date(2026, 8, 24)) == "SPRE260824.zip"
    assert pregao_filelist("028", date(2026, 8, 24)) == "IN260824.zip"


def test_validate_rejects_empty_zip() -> None:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w"):
        pass
    payload = buffer.getvalue()
    assert len(payload) < 100
    with pytest.raises(B3ParseError):
        validate_b3_zip(payload)


def test_validate_rejects_garbage_bytes() -> None:
    with pytest.raises(B3ParseError):
        validate_b3_zip(b"<html>not a zip</html>")


def test_parse_lastpric_as_last_decimal() -> None:
    xml = (FIXTURES / "price_report.xml").read_text(encoding="utf-8")
    payload = _nested_zip("SPRE260824.zip", "BVBG.186.01_sample.xml", xml.encode("utf-8"))
    records = parse_price_report(payload)
    assert len(records) == 1
    petr4 = records[0]
    assert petr4.reference_date == date(2026, 8, 24)
    assert petr4.last_price == Decimal("42.11")
    assert petr4.security_id == "200003061028"
    assert petr4.currency == "BRL"
    skipped = [item for item in records if item.ticker == "NOBID11"]
    assert skipped == []


def test_parse_instrument_master_isin() -> None:
    xml = (FIXTURES / "instrument_master.xml").read_text(encoding="utf-8")
    payload = _nested_zip("IN260824.zip", "BVBG.028.02_sample.xml", xml.encode("utf-8"))
    by_ticker = parse_instrument_master(payload)
    assert by_ticker["PETR4"].isin == "BRPETRACNPR6"
    assert by_ticker["PETR4"].ticker == "PETR4"
