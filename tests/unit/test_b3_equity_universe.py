from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from marketdata.config import Settings
from marketdata.ingestion.universe import (
    b3_equity_allowlist,
    equity_last_records_to_persist,
    live_otc_credit_enabled,
    load_b3_equity_tickers,
    resolve_b3_equity_universe_path,
    should_persist_b3_equity_last,
)
from marketdata.providers.b3 import (
    B3PriceRecord,
    is_mvp_future_ticker,
    parse_price_report,
    parse_settlement_report,
)

ROOT = Path(__file__).resolve().parents[2]
SCRATCH_CSV = ROOT / "config" / "instruments.scratch.csv"
TINY_CSV = Path(__file__).resolve().parents[1] / "fixtures" / "coverage" / "universe.tiny.csv"
B3_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "b3"
UNIVERSE_HEADER = (
    "instrument_id,asset_class,ticker,isin,cnpj_fundo_classe,title_type,"
    "maturity_date,exchange,currency,preferred_provider,universe\n"
)


def _settings(**kwargs: str) -> Settings:
    return Settings(_env_file=None, **kwargs)


def _last(ticker: str, price: str = "10.00") -> B3PriceRecord:
    return B3PriceRecord(
        ticker=ticker,
        reference_date=date(2026, 8, 24),
        last_price=Decimal(price),
        security_id=None,
        currency="BRL",
        extra={},
    )


def _nested_zip(outer_name: str, inner_name: str, xml: bytes) -> bytes:
    inner_buffer = BytesIO()
    with ZipFile(inner_buffer, "w") as inner:
        inner.writestr(inner_name, xml)
    outer_buffer = BytesIO()
    with ZipFile(outer_buffer, "w") as outer:
        outer.writestr(outer_name, inner_buffer.getvalue())
    return outer_buffer.getvalue()


def test_settings_universe_opt_in_defaults_off() -> None:
    settings = _settings()
    assert settings.ingest_universe == ""
    assert settings.b3_equity_universe_path == ""
    assert resolve_b3_equity_universe_path(settings) is None
    assert b3_equity_allowlist(settings) is None


def test_in_list_equity_ticker_is_kept() -> None:
    allowlist = load_b3_equity_tickers(TINY_CSV)
    assert "PETR4" in allowlist
    quotes = [_last("PETR4", "42.11"), _last("ZZZZ3")]
    persisted = equity_last_records_to_persist(quotes, allowlist)
    assert [record.ticker for record in persisted] == ["PETR4"]
    assert should_persist_b3_equity_last("PETR4", allowlist) is True


def test_out_of_list_equity_ticker_is_skipped() -> None:
    allowlist = load_b3_equity_tickers(TINY_CSV)
    assert "VALE3" not in allowlist
    quotes = [_last("PETR4"), _last("VALE3"), _last("AAPL")]
    persisted = equity_last_records_to_persist(quotes, allowlist)
    assert [record.ticker for record in persisted] == ["PETR4"]
    assert should_persist_b3_equity_last("VALE3", allowlist) is False
    assert should_persist_b3_equity_last("AAPL", allowlist) is False


def test_default_off_full_186_behavior_unchanged() -> None:
    xml = (B3_FIXTURES / "price_report.xml").read_bytes()
    payload = _nested_zip("SPRE260824.zip", "BVBG.186.01_sample.xml", xml)
    quotes = parse_price_report(payload)
    assert [record.ticker for record in quotes] == ["PETR4"]
    extra = [*quotes, _last("VALE3"), _last("NOBID11")]
    assert b3_equity_allowlist(_settings()) is None
    persisted = equity_last_records_to_persist(extra, None)
    assert [record.ticker for record in persisted] == ["PETR4", "VALE3", "NOBID11"]


def test_futures_187_unchanged_when_allowlist_on() -> None:
    allowlist = load_b3_equity_tickers(TINY_CSV)
    assert "DI1F27" not in allowlist
    xml = (B3_FIXTURES / "derivatives_price_report.xml").read_bytes()
    payload = _nested_zip("SPRD260824.zip", "BVBG.187.01_sample.xml", xml)
    settlements = [
        record for record in parse_settlement_report(payload) if is_mvp_future_ticker(record.ticker)
    ]
    tickers = {record.ticker for record in settlements}
    assert "DI1F27" in tickers
    assert "DOLG27" in tickers
    assert "BGIF27C1234" not in tickers
    assert "WINQ26" not in tickers
    assert all(is_mvp_future_ticker(record.ticker) for record in settlements)
    # Equity allowlist must not be applied to 187; DI1F27 is absent from the CSV equities.
    assert should_persist_b3_equity_last("DI1F27", allowlist) is False


def test_scratch_reads_scratch_csv_b3_equities_only() -> None:
    settings = _settings(ingest_universe="scratch")
    path = resolve_b3_equity_universe_path(settings, base=ROOT)
    assert path == SCRATCH_CSV
    allowlist = b3_equity_allowlist(settings, base=ROOT)
    assert allowlist is not None
    assert "PETR4" in allowlist
    assert "VALE3" in allowlist
    assert "AAPL" not in allowlist
    assert "DI1F27" not in allowlist
    persisted = equity_last_records_to_persist(
        [_last("PETR4"), _last("AAPL"), _last("FAKE9")],
        allowlist,
    )
    assert [record.ticker for record in persisted] == ["PETR4"]


def test_scratch_prefers_operator_instruments_csv(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "instruments.example.csv").write_text(
        UNIVERSE_HEADER + ",equity,PETR4,,,,,B3,BRL,b3,ibov\n",
        encoding="utf-8",
    )
    (config / "instruments.csv").write_text(
        UNIVERSE_HEADER + ",equity,WEGE3,,,,,B3,BRL,b3,ibov\n",
        encoding="utf-8",
    )
    settings = _settings(ingest_universe="scratch")
    allowlist = b3_equity_allowlist(settings, base=tmp_path)
    assert allowlist == frozenset({"WEGE3"})
    assert should_persist_b3_equity_last("WEGE3", allowlist) is True
    assert should_persist_b3_equity_last("PETR4", allowlist) is False


def test_explicit_path_wins_over_scratch() -> None:
    settings = _settings(
        ingest_universe="scratch",
        b3_equity_universe_path=str(TINY_CSV),
    )
    path = resolve_b3_equity_universe_path(settings, base=ROOT)
    assert path == TINY_CSV
    allowlist = b3_equity_allowlist(settings, base=ROOT)
    assert allowlist is not None
    assert "PETR4" in allowlist
    assert "UNKNOWN1" in allowlist
    assert "VALE3" not in allowlist


def test_scratch_allowlist_disables_live_otc_credit() -> None:
    assert live_otc_credit_enabled(None) is True
    assert live_otc_credit_enabled(frozenset({"PETR4"})) is False


def test_unknown_ingest_universe_is_rejected() -> None:
    settings = _settings(ingest_universe="ibov")
    with pytest.raises(ValueError, match="unknown INGEST_UNIVERSE"):
        resolve_b3_equity_universe_path(settings)
