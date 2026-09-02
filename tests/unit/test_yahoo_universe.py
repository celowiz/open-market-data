from pathlib import Path

from marketdata.config import Settings
from marketdata.coverage.csv import UniverseRow
from marketdata.ingestion.yahoo_universe import (
    YAHOO_FUTURE_PREFIXES,
    default_yahoo_symbols,
    default_yahoo_universe_path,
    load_yahoo_universe_symbols,
    to_yahoo_symbol,
    yahoo_span_alias,
)

ROOT = Path(__file__).resolve().parents[2]
SCRATCH_CSV = ROOT / "config" / "instruments.scratch.csv"
UNIVERSE_HEADER = (
    "instrument_id,asset_class,ticker,isin,cnpj_fundo_classe,title_type,"
    "maturity_date,exchange,currency,preferred_provider,universe\n"
)


def test_equity_ticker_maps_to_yahoo_sa_suffix() -> None:
    assert to_yahoo_symbol("PETR4") == "PETR4.SA"
    assert to_yahoo_symbol(" petr4 ") == "PETR4.SA"


def test_existing_yahoo_suffix_is_not_doubled() -> None:
    assert to_yahoo_symbol("PETR4.SA") == "PETR4.SA"


def test_scratch_universe_maps_equities_skips_futures_and_does_not_default_aapl(
    tmp_path: Path,
) -> None:
    path = tmp_path / "universe.csv"
    path.write_text(
        UNIVERSE_HEADER
        + ",equity,PETR4,,,,,B3,BRL,b3,ibov\n"
        + ",equity,VALE3,,,,,B3,BRL,b3,ibov\n"
        + ",future,WINV26,,,,2026-10-21,B3,BRL,b3,b3_futures\n"
        + ",future,INDZ26,,,,2026-12-16,B3,BRL,b3,b3_futures\n"
        + ",future,WDOU26,,,,2026-09-01,B3,BRL,b3,b3_futures\n"
        + ",future,DOLV26,,,,2026-10-01,B3,BRL,b3,b3_futures\n"
        + ",future,DI1F27,,,,2027-01-04,B3,BRL,b3,b3_futures\n",
        encoding="utf-8",
    )
    selection = load_yahoo_universe_symbols(path)
    assert selection.symbols == ["PETR4.SA", "VALE3.SA"]
    assert selection.skipped_futures == 5
    assert "AAPL" not in selection.symbols
    assert all(symbol.endswith(".SA") for symbol in selection.symbols)


def test_scratch_csv_has_150_sa_equities_and_skips_listed_futures() -> None:
    selection = load_yahoo_universe_symbols(SCRATCH_CSV)
    assert len(selection.symbols) == 150
    assert selection.skipped_futures == 15
    assert "PETR4.SA" in selection.symbols
    assert "AAPL" not in selection.symbols
    assert all(symbol.endswith(".SA") for symbol in selection.symbols)
    assert not any(
        symbol.split(".", 1)[0].startswith(YAHOO_FUTURE_PREFIXES) for symbol in selection.symbols
    )
    defaults = default_yahoo_symbols()
    assert defaults[: len(selection.symbols)] == selection.symbols
    assert "CL=F" in defaults
    assert "GC=F" in defaults
    assert "HG=F" in defaults
    assert "DX-Y.NYB" in defaults
    assert "BRL=X" in defaults
    assert "AAPL" not in defaults
    assert defaults[0] != "AAPL"


def test_yahoo_span_alias_maps_b3_equity_only() -> None:
    petr = UniverseRow(
        instrument_id=None,
        asset_class="equity",
        ticker="PETR4",
        isin=None,
        cnpj_fundo_classe=None,
        title_type=None,
        maturity_date=None,
        exchange="B3",
        currency="BRL",
        preferred_provider="b3",
        universe="ibov",
    )
    aapl = UniverseRow(
        instrument_id=None,
        asset_class="equity",
        ticker="AAPL",
        isin=None,
        cnpj_fundo_classe=None,
        title_type=None,
        maturity_date=None,
        exchange="NASDAQ",
        currency="USD",
        preferred_provider="yahoo",
        universe="djia",
    )
    future = UniverseRow(
        instrument_id=None,
        asset_class="future",
        ticker="WINV26",
        isin=None,
        cnpj_fundo_classe=None,
        title_type=None,
        maturity_date=None,
        exchange="B3",
        currency="BRL",
        preferred_provider="b3",
        universe="b3_futures",
    )
    assert yahoo_span_alias(petr) == "PETR4.SA"
    assert yahoo_span_alias(aapl) is None
    assert yahoo_span_alias(future) is None


def test_default_yahoo_universe_stays_scratch_when_ingest_universe_unset(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "instruments.scratch.csv").write_text(
        UNIVERSE_HEADER + ",equity,PETR4,,,,,B3,BRL,b3,ibov\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=None, coverage_config_dir=str(tmp_path), ingest_universe="")
    path = default_yahoo_universe_path(settings)
    assert path.name == "instruments.scratch.csv"
    assert load_yahoo_universe_symbols(path).symbols == ["PETR4.SA"]


def test_default_yahoo_universe_honors_explicit_b3_equity_path(tmp_path: Path) -> None:
    csv_path = tmp_path / "custom.csv"
    csv_path.write_text(
        UNIVERSE_HEADER + ",equity,VALE3,,,,,B3,BRL,b3,ibov\n",
        encoding="utf-8",
    )
    settings = Settings(
        _env_file=None,
        ingest_universe="scratch",
        b3_equity_universe_path=str(csv_path),
    )
    path = default_yahoo_universe_path(settings)
    assert path == csv_path
    assert load_yahoo_universe_symbols(path).symbols == ["VALE3.SA"]
