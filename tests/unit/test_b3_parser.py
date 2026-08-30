from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from marketdata.config import Settings
from marketdata.providers.b3 import (
    B3ParseError,
    b3_http_timeout,
    is_mvp_future_ticker,
    parse_instrument_master,
    parse_price_report,
    parse_settlement_report,
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
    assert pregao_filelist("187", date(2026, 8, 24)) == "SPRD260824.zip"


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


def test_parse_instrument_master_futures_isin_and_maturity() -> None:
    xml = (FIXTURES / "instrument_master.xml").read_text(encoding="utf-8")
    payload = _nested_zip("IN260824.zip", "BVBG.028.02_sample.xml", xml.encode("utf-8"))
    by_ticker = parse_instrument_master(payload)
    di1 = by_ticker["DI1F27"]
    assert di1.isin == "BRBMEFD1I4Z0"
    assert di1.maturity_date == date(2027, 1, 4)
    assert di1.currency == "BRL"


def test_parse_settlement_uses_adjstdqt_not_lastpric() -> None:
    xml = (FIXTURES / "derivatives_price_report.xml").read_bytes()
    payload = _nested_zip("SPRD260824.zip", "BVBG.187.01_sample.xml", xml)
    records = parse_settlement_report(payload)
    by_ticker = {item.ticker: item for item in records}
    di1 = by_ticker["DI1F27"]
    assert di1.reference_date == date(2026, 8, 24)
    assert di1.settlement == Decimal("89656.53")
    assert di1.unit == "PU"
    assert di1.security_id == "200000891646"
    assert di1.currency == "BRL"
    assert di1.extra["AdjstdQtTax"] == "13.789"
    assert di1.extra["PrvsAdjstdQt"] == "89621.42"
    assert di1.extra["LastPric"] == "13.81"
    assert di1.settlement != Decimal("13.81")
    assert "WINQ26" not in by_ticker
    assert by_ticker["DOLG27"].settlement == Decimal("5146.559")


def test_parse_settlement_dedupes_duplicate_xml_blobs() -> None:
    xml = (FIXTURES / "derivatives_price_report.xml").read_bytes()
    inner_buffer = BytesIO()
    with ZipFile(inner_buffer, "w") as inner:
        inner.writestr("BVBG.187.01_a.xml", xml)
        inner.writestr("BVBG.187.01_b.xml", xml)
    outer_buffer = BytesIO()
    with ZipFile(outer_buffer, "w") as outer:
        outer.writestr("SPRD260824.zip", inner_buffer.getvalue())
    records = parse_settlement_report(outer_buffer.getvalue())
    di1 = [item for item in records if item.ticker == "DI1F27"]
    assert len(di1) == 1
    assert di1[0].settlement == Decimal("89656.53")


def test_parse_instrument_master_uses_first_xml_blob_only() -> None:
    first = (FIXTURES / "instrument_master.xml").read_bytes()
    second = first.replace(b"PETR4", b"EXTRA9", 1)
    inner_buffer = BytesIO()
    with ZipFile(inner_buffer, "w") as inner:
        inner.writestr("BVBG.028.02_a.xml", first)
        inner.writestr("BVBG.028.02_b.xml", second)
    outer_buffer = BytesIO()
    with ZipFile(outer_buffer, "w") as outer:
        outer.writestr("IN260824.zip", inner_buffer.getvalue())
    by_ticker = parse_instrument_master(outer_buffer.getvalue())
    assert "PETR4" in by_ticker
    assert "EXTRA9" not in by_ticker


def test_parse_instrument_master_keep_tickers_filters_and_keeps_isin() -> None:
    xml = (FIXTURES / "instrument_master.xml").read_text(encoding="utf-8")
    extra = xml.replace(
        "</EqtyInf>",
        "</EqtyInf>\n            <EqtyInf>"
        "<ISIN>BRVALEACNOR0</ISIN>"
        "<TckrSymb>EXTRA9</TckrSymb>"
        "<CrpnNm>EXTRA</CrpnNm>"
        "<TradgCcy>BRL</TradgCcy>"
        "</EqtyInf>",
        1,
    )
    payload = _nested_zip("IN260824.zip", "BVBG.028.02_sample.xml", extra.encode("utf-8"))
    full = parse_instrument_master(payload)
    assert "PETR4" in full
    assert "EXTRA9" in full
    filtered = parse_instrument_master(payload, keep_tickers=frozenset({"PETR4"}))
    assert set(filtered) == {"PETR4"}
    assert filtered["PETR4"].isin == "BRPETRACNPR6"


def test_b3_http_timeout_bounds_connect_and_read() -> None:
    timeout = b3_http_timeout(Settings(_env_file=None, http_timeout_seconds=30))
    assert timeout.connect == 15.0
    assert timeout.read == 60.0
    assert timeout.write == 30.0
    long_read = b3_http_timeout(Settings(_env_file=None, http_timeout_seconds=180))
    assert long_read.read == 180.0


def test_mvp_future_ticker_allowlist() -> None:
    assert is_mvp_future_ticker("DI1F27")
    assert is_mvp_future_ticker("DOLG27")
    assert is_mvp_future_ticker("WDOZ26")
    assert is_mvp_future_ticker("WING27")
    assert is_mvp_future_ticker("INDV26")
    assert not is_mvp_future_ticker("BGIF27C1234")
    assert not is_mvp_future_ticker("PETR4")
    assert not is_mvp_future_ticker("FRCF33")
