from collections.abc import Sequence
from pathlib import Path

from marketdata.config import Settings, get_settings
from marketdata.coverage.csv import load_universe
from marketdata.coverage.paths import default_universe_path
from marketdata.providers.b3 import B3PriceRecord

SCRATCH_UNIVERSE = "scratch"
_B3_EXCHANGE = "B3"
_EQUITY = "equity"


def resolve_b3_equity_universe_path(
    settings: Settings | None = None,
    *,
    base: Path | None = None,
) -> Path | None:
    """Return the CSV used to filter BVBG.186 LAST, or None when the filter is off."""
    cfg = settings if settings is not None else get_settings()
    explicit = cfg.b3_equity_universe_path.strip()
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise FileNotFoundError(f"B3_EQUITY_UNIVERSE_PATH is not a file: {path}")
        return path
    raw = cfg.ingest_universe.strip().lower()
    if not raw:
        return None
    if raw != SCRATCH_UNIVERSE:
        raise ValueError(
            f"unknown INGEST_UNIVERSE={cfg.ingest_universe!r}; "
            "use 'scratch' or leave empty for full B3 BVBG.186"
        )
    root = base if base is not None else Path(cfg.coverage_config_dir)
    path = default_universe_path(root)
    if not path.is_file():
        raise FileNotFoundError(f"INGEST_UNIVERSE=scratch but universe CSV is missing: {path}")
    return path


def load_b3_equity_tickers(path: Path) -> frozenset[str]:
    """B3 equity tickers from a coverage-universe CSV (IBOV+SMLL in the example seed)."""
    return frozenset(
        row.ticker.strip().upper()
        for row in load_universe(path)
        if row.ticker
        and row.asset_class.strip().lower() == _EQUITY
        and (row.exchange or "").strip().upper() == _B3_EXCHANGE
    )


def b3_equity_allowlist(
    settings: Settings | None = None,
    *,
    base: Path | None = None,
) -> frozenset[str] | None:
    """Tickers to persist from BVBG.186 LAST, or None when ingest is unfiltered."""
    path = resolve_b3_equity_universe_path(settings, base=base)
    if path is None:
        return None
    return load_b3_equity_tickers(path)


def should_persist_b3_equity_last(ticker: str, allowlist: frozenset[str] | None) -> bool:
    if allowlist is None:
        return True
    return ticker.strip().upper() in allowlist


def equity_last_records_to_persist(
    quotes: Sequence[B3PriceRecord],
    allowlist: frozenset[str] | None,
) -> list[B3PriceRecord]:
    return [record for record in quotes if should_persist_b3_equity_last(record.ticker, allowlist)]
