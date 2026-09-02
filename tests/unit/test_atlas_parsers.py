from datetime import date
from decimal import Decimal
from pathlib import Path

from marketdata.ingestion.config_tables import (
    load_cot_contracts,
    load_scratch_cusip_map,
    load_scratch_issuers,
)
from marketdata.providers.b3_lending import (
    LENDING_OPEN_POSITION,
    LENDING_REGISTERED,
    negociosbtb_urls,
    parse_lending_table,
)
from marketdata.providers.cftc import parse_cot_rows
from marketdata.providers.cvm_events import parse_fato_relevante_csv
from marketdata.providers.edgar import parse_13f_information_table
from marketdata.providers.fred import parse_fred_observations
from marketdata.providers.ibge import parse_sidra_observations

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def test_parse_lending_open_filters_scratch_and_keeps_qty() -> None:
    payload = (FIXTURES / "b3" / "lending_open.json").read_bytes()
    records = parse_lending_table(
        payload,
        snapshot_type=LENDING_OPEN_POSITION,
        reference_date=date(2026, 8, 21),
        allowlist=frozenset({"PETR4", "VALE3"}),
    )
    by_ticker = {row.ticker: row for row in records}
    assert set(by_ticker) == {"PETR4", "VALE3"}
    assert "OUTR4" not in by_ticker
    assert by_ticker["PETR4"].qty == Decimal("12000000")
    assert by_ticker["PETR4"].avg_price == Decimal("38.50")
    assert by_ticker["PETR4"].snapshot_type == LENDING_OPEN_POSITION


def test_parse_lending_registered_qty_rate_contracts() -> None:
    payload = (FIXTURES / "b3" / "lending_registered.json").read_bytes()
    records = parse_lending_table(
        payload,
        snapshot_type=LENDING_REGISTERED,
        reference_date=date(2026, 8, 21),
        allowlist=frozenset({"PETR4"}),
    )
    assert len(records) == 1
    row = records[0]
    assert row.ticker == "PETR4"
    assert row.qty == Decimal("1500000")
    assert row.avg_rate == Decimal("0.12")
    assert row.contracts == 42


def test_negociosbtb_url_templates_are_documented() -> None:
    urls = negociosbtb_urls(date(2026, 8, 21))
    assert any("Trade_SecuritiesLending_TradeSecuritiesLendingFile" in url for url in urls)
    assert any("21082026_NEGOCIOSBTB.zip" in url for url in urls)


def test_parse_fred_skips_dot_missing_values() -> None:
    payload = (FIXTURES / "fred" / "dgs10.json").read_bytes()
    rows = parse_fred_observations("DGS10", payload)
    assert [row.reference_date for row in rows] == [date(2026, 8, 20), date(2026, 8, 21)]
    assert rows[-1].value == Decimal("4.05")


def test_parse_sidra_ipca_month() -> None:
    payload = (FIXTURES / "ibge" / "ipca.json").read_bytes()
    rows = parse_sidra_observations(
        payload=payload,
        code="IBGE:IPCA_MOM",
        source_series_id="1737:63",
        name="IPCA",
        unit="percent",
    )
    assert len(rows) == 1
    assert rows[0].reference_date == date(2026, 8, 1)
    assert rows[0].value == Decimal("0.43")


def test_parse_fato_relevante_filters_scratch_cnpj() -> None:
    payload = (FIXTURES / "cvm" / "fato_relevante.csv").read_bytes()
    issuers = load_scratch_issuers()
    rows = parse_fato_relevante_csv(payload, issuers=issuers)
    assert len(rows) == 1
    assert rows[0].ticker == "PETR4"
    assert "pre-sal" in rows[0].headline
    assert rows[0].url is not None
    assert "body" not in rows[0].headline.lower()


def test_parse_cot_allowlist_drops_corn() -> None:
    payload = (FIXTURES / "cftc" / "cot.json").read_bytes()
    rows = parse_cot_rows(payload, load_cot_contracts())
    codes = {row.contract_code for row in rows}
    assert codes == {"SPX", "CL"}
    assert all(row.open_interest is not None for row in rows)


def test_lending_allowlist_defaults_to_scratch_when_universe_empty(monkeypatch) -> None:
    from marketdata.config import Settings
    from marketdata.ingestion.universe import lending_equity_allowlist

    monkeypatch.setattr(
        "marketdata.ingestion.universe.get_settings",
        lambda: Settings(_env_file=None, ingest_universe="", b3_equity_universe_path=""),
    )
    tickers = lending_equity_allowlist(Settings(_env_file=None, ingest_universe=""))
    assert "PETR4" in tickers
    assert "VALE3" in tickers
    assert len(tickers) >= 150


def test_parse_13f_keeps_only_mapped_cusip() -> None:
    payload = (FIXTURES / "edgar" / "13f.xml").read_bytes()
    mapping = load_scratch_cusip_map()
    rows = parse_13f_information_table(
        payload,
        filer_cik="0001067983",
        filer_name="Berkshire",
        report_date=date(2026, 6, 30),
        cusip_map=mapping,
    )
    assert len(rows) == 1
    assert rows[0].ticker == "PETR4"
    assert rows[0].cusip == "71654V408"
    assert rows[0].shares == Decimal("1000000")
