from pathlib import Path

from marketdata.ingestion.yahoo_universe import (
    YAHOO_FUTURE_PREFIXES,
    default_yahoo_symbols,
    load_yahoo_universe_symbols,
    to_yahoo_symbol,
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
    assert defaults == selection.symbols
    assert defaults[0] != "AAPL"
