from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from marketdata.config import get_settings
from marketdata.coverage.csv import load_universe
from marketdata.coverage.paths import SCRATCH_UNIVERSE, named_universe_path

YAHOO_FUTURE_PREFIXES = ("WIN", "IND", "WDO", "DOL", "DI1")
_FUTURE = "future"
_EQUITY = "equity"


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


def default_yahoo_universe_path() -> Path:
    settings = get_settings()
    return named_universe_path(SCRATCH_UNIVERSE, base=Path(settings.coverage_config_dir))


def default_yahoo_symbols(path: Path | None = None) -> list[str]:
    csv_path = path if path is not None else default_yahoo_universe_path()
    return load_yahoo_universe_symbols(csv_path).symbols
