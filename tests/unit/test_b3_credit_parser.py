import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx

from marketdata.providers.b3 import (
    BDI_CREDIT_MASTER_TABLE,
    BDI_CREDIT_TRADES_TABLE,
    BDI_EXPORT_URL,
    B3Provider,
    parse_otc_instrument_file,
    parse_otc_trade_file,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "b3"


def test_parse_otc_trades_maps_closing_to_last_decimal_not_reference() -> None:
    records = parse_otc_trade_file((FIXTURES / "otc_trades.json").read_bytes())
    by_ticker = {item.ticker: item for item in records}
    jall = by_ticker["JALL14"]
    assert jall.reference_date == date(2026, 8, 21)
    assert jall.last_price == Decimal("1133.31")
    assert jall.last_price != Decimal("9999.00")
    assert jall.isin == "BRJALLDBS036"
    assert jall.instrument_type == "debenture"
    assert jall.extra["ReferencePrice"] == "9999.00"
    assert jall.extra["BusinessClass"] == "EXTRAGRUPO"


def test_parse_otc_trades_collapses_groupings_and_filters_types() -> None:
    records = parse_otc_trade_file((FIXTURES / "otc_trades.json").read_bytes())
    tickers = [item.ticker for item in records]
    assert tickers.count("JALL14") == 1
    assert "CDB123" not in tickers
    assert "NOTRADE1" not in tickers
    assert "EMPTYCLS" not in tickers
    by_ticker = {item.ticker: item for item in records}
    assert by_ticker["VIRG24"].instrument_type == "cri"
    assert by_ticker["VIRG24"].last_price == Decimal("1012.417662")
    assert by_ticker["CRA0240086L"].instrument_type == "cra"
    assert by_ticker["CRA0240086L"].last_price == Decimal("953.459831")


def test_parse_otc_instruments_filters_credit_types() -> None:
    records = parse_otc_instrument_file((FIXTURES / "otc_instruments.json").read_bytes())
    by_ticker = {item.ticker: item for item in records}
    assert "CDB123" not in by_ticker
    silent = by_ticker["SILENT1"]
    assert silent.instrument_type == "debenture"
    assert silent.isin == "BRSILNDBS001"
    assert silent.maturity_date == date(2029, 5, 20)
    assert by_ticker["JALL14"].name == "JALLES MACHADO S.A."


def test_parse_otc_trades_csv_maps_ultimo_preco() -> None:
    csv_payload = (
        b"TckrSymb;InstrumentCode;TradeDate;Closing;NumberOfTrades;ReferencePrice;BusinessClass\n"
        b"JALL14;DEB;2026-08-21;1133.31;1;9999.00;EXTRAGRUPO\n"
        b"CDB123;CDB;2026-08-21;1000;1;1000;-\n"
    )
    records = parse_otc_trade_file(csv_payload)
    assert len(records) == 1
    assert records[0].ticker == "JALL14"
    assert records[0].last_price == Decimal("1133.31")


def test_fetch_public_table_posts_bdi_export() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=b'{"columns":[],"values":[]}')

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = B3Provider().fetch_public_table(
        BDI_CREDIT_TRADES_TABLE, date(2026, 8, 21), client=client
    )
    assert captured["url"] == BDI_EXPORT_URL
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["Name"] == BDI_CREDIT_TRADES_TABLE
    assert body["Date"] == "2026-08-21"
    assert body["FinalDate"] == "2026-08-21"
    assert response.status_code == 200
    assert BDI_CREDIT_MASTER_TABLE == "InstrumentRegistration"
