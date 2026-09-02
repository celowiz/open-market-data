from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from marketdata.config import Settings, get_settings
from marketdata.coverage.csv import UniverseRow, load_universe
from marketdata.coverage.paths import SCRATCH_UNIVERSE, named_universe_path
from marketdata.ingestion.config_tables import load_yahoo_macro_symbols
from marketdata.ingestion.universe import resolve_b3_equity_universe_path

YAHOO_FUTURE_PREFIXES = ("WIN", "IND", "WDO", "DOL", "DI1")
_FUTURE = "future"
_EQUITY = "equity"
_B3 = "B3"


@dataclass(frozen=True)
class YahooUniverseSelection:
    symbols: list[str]
    skipped_futures: int


def to_yahoo_symbol(ticker: str) -> str:
    text = ticker.strip().upper()
    if not text:
        return text
    if "." in text:
        return text
    return f"{text}.SA"


def is_yahoo_future(ticker: str, asset_class: str = "") -> bool:
    if asset_class.strip().lower() == _FUTURE:
        return True
    return ticker.strip().upper().startswith(YAHOO_FUTURE_PREFIXES)


def yahoo_span_alias(row: UniverseRow) -> str | None:
    """Yahoo `{TICKER}.SA` companion for a B3 equity coverage row, else None."""
    if row.asset_class.strip().lower() != _EQUITY:
        return None
    if is_yahoo_future(row.ticker, row.asset_class):
        return None
    exchange = (row.exchange or "").strip().upper()
    preferred = (row.preferred_provider or "").strip().lower()
    if exchange != _B3 and preferred != "b3":
        return None
    symbol = to_yahoo_symbol(row.ticker)
    if not symbol or symbol == row.ticker.strip().upper():
        return None
    return symbol


def load_yahoo_universe_symbols(path: Path) -> YahooUniverseSelection:
    symbols: list[str] = []
    skipped = 0
    seen: set[str] = set()
    for row in load_universe(path):
        ticker = (row.ticker or "").strip()
        if not ticker:
            continue
        if is_yahoo_future(ticker, row.asset_class):
            skipped += 1
            continue
        if row.asset_class.strip().lower() != _EQUITY:
            continue
        symbol = to_yahoo_symbol(ticker)
        if symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return YahooUniverseSelection(symbols=symbols, skipped_futures=skipped)


def default_yahoo_universe_path(settings: Settings | None = None) -> Path:
    cfg = settings if settings is not None else get_settings()
    explicit = resolve_b3_equity_universe_path(cfg)
    if explicit is not None:
        return explicit
    return named_universe_path(SCRATCH_UNIVERSE, base=Path(cfg.coverage_config_dir))


def default_yahoo_symbols(path: Path | None = None) -> list[str]:
    csv_path = path if path is not None else default_yahoo_universe_path()
    symbols = list(load_yahoo_universe_symbols(csv_path).symbols)
    seen = set(symbols)
    for row in load_yahoo_macro_symbols():
        if row.symbol not in seen:
            seen.add(row.symbol)
            symbols.append(row.symbol)
    return symbols
