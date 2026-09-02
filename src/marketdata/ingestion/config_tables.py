from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from marketdata.config import get_settings


def _root() -> Path:
    return Path(get_settings().coverage_config_dir)


def _read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, comment_prefix="#", infer_schema_length=0)


@dataclass(frozen=True)
class FredSeriesSpec:
    series_id: str
    code: str
    name: str
    asset_class: str
    unit: str
    currency: str


@dataclass(frozen=True)
class YahooMacroSymbol:
    symbol: str
    name: str
    asset_class: str
    currency: str


@dataclass(frozen=True)
class CotContractSpec:
    code: str
    name_contains: str
    kind: str


def load_fred_series(path: Path | None = None) -> list[FredSeriesSpec]:
    csv_path = path or _root() / "config" / "fred_series.csv"
    rows: list[FredSeriesSpec] = []
    for record in _read_csv(csv_path).iter_rows(named=True):
        series_id = str(record.get("series_id") or "").strip()
        if not series_id:
            continue
        rows.append(
            FredSeriesSpec(
                series_id=series_id,
                code=str(record.get("code") or f"FRED:{series_id}").strip(),
                name=str(record.get("name") or series_id).strip(),
                asset_class=str(record.get("asset_class") or "other").strip().lower(),
                unit=str(record.get("unit") or "index").strip(),
                currency=str(record.get("currency") or "USD").strip(),
            )
        )
    return rows


def load_yahoo_macro_symbols(path: Path | None = None) -> list[YahooMacroSymbol]:
    csv_path = path or _root() / "config" / "yahoo_macro.csv"
    if not csv_path.is_file():
        return []
    rows: list[YahooMacroSymbol] = []
    seen: set[str] = set()
    for record in _read_csv(csv_path).iter_rows(named=True):
        symbol = str(record.get("symbol") or "").strip()
        if not symbol or symbol.upper() == "AAPL" or symbol in seen:
            continue
        seen.add(symbol)
        rows.append(
            YahooMacroSymbol(
                symbol=symbol,
                name=str(record.get("name") or symbol).strip(),
                asset_class=str(record.get("asset_class") or "other").strip().lower(),
                currency=str(record.get("currency") or "USD").strip(),
            )
        )
    return rows


def load_scratch_issuers(path: Path | None = None) -> dict[str, str]:
    """Map digits-only CNPJ -> ticker (first ticker wins per CNPJ, ticker->cnpj also)."""
    csv_path = path or _root() / "config" / "scratch_issuers.csv"
    if not csv_path.is_file():
        return {}
    cnpj_to_ticker: dict[str, str] = {}
    for record in _read_csv(csv_path).iter_rows(named=True):
        ticker = str(record.get("ticker") or "").strip().upper()
        cnpj = "".join(ch for ch in str(record.get("cnpj") or "") if ch.isdigit())
        if ticker and cnpj and cnpj not in cnpj_to_ticker:
            cnpj_to_ticker[cnpj] = ticker
    return cnpj_to_ticker


def load_scratch_cusip_map(path: Path | None = None) -> dict[str, str]:
    """Map CUSIP -> scratch ticker."""
    csv_path = path or _root() / "config" / "scratch_cusip.csv"
    if not csv_path.is_file():
        return {}
    mapping: dict[str, str] = {}
    for record in _read_csv(csv_path).iter_rows(named=True):
        cusip = str(record.get("cusip") or "").strip().upper()
        ticker = str(record.get("ticker") or "").strip().upper()
        if cusip and ticker:
            mapping[cusip] = ticker
    return mapping


def load_cot_contracts(path: Path | None = None) -> list[CotContractSpec]:
    csv_path = path or _root() / "config" / "cot_contracts.csv"
    rows: list[CotContractSpec] = []
    for record in _read_csv(csv_path).iter_rows(named=True):
        code = str(record.get("code") or "").strip().upper()
        contains = str(record.get("name_contains") or "").strip()
        if not code or not contains:
            continue
        rows.append(
            CotContractSpec(
                code=code,
                name_contains=contains,
                kind=str(record.get("kind") or "").strip(),
            )
        )
    return rows
