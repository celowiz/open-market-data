from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

import polars as pl

UNIVERSE_COLUMNS = (
    "instrument_id",
    "asset_class",
    "ticker",
    "isin",
    "cnpj_fundo_classe",
    "title_type",
    "maturity_date",
    "exchange",
    "currency",
    "preferred_provider",
    "universe",
)


@dataclass(frozen=True)
class UniverseRow:
    instrument_id: UUID | None
    asset_class: str
    ticker: str
    isin: str | None
    cnpj_fundo_classe: str | None
    title_type: str | None
    maturity_date: date | None
    exchange: str | None
    currency: str | None
    preferred_provider: str
    universe: str | None = None


def _blank(value: object) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _parse_uuid(value: str | None) -> UUID | None:
    if value is None:
        return None
    return UUID(value)


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def load_universe(path: Path) -> list[UniverseRow]:
    frame = pl.read_csv(path, comment_prefix="#", infer_schema_length=0)
    missing = [column for column in UNIVERSE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"universe CSV missing columns: {missing}")
    rows: list[UniverseRow] = []
    for record in frame.select(list(UNIVERSE_COLUMNS)).iter_rows(named=True):
        ticker = _blank(record["ticker"]) or ""
        asset_class = _blank(record["asset_class"]) or ""
        preferred_provider = _blank(record["preferred_provider"]) or ""
        rows.append(
            UniverseRow(
                instrument_id=_parse_uuid(_blank(record["instrument_id"])),
                asset_class=asset_class,
                ticker=ticker,
                isin=_blank(record["isin"]),
                cnpj_fundo_classe=_blank(record["cnpj_fundo_classe"]),
                title_type=_blank(record["title_type"]),
                maturity_date=_parse_date(_blank(record["maturity_date"])),
                exchange=_blank(record["exchange"]),
                currency=_blank(record["currency"]),
                preferred_provider=preferred_provider,
                universe=_blank(record["universe"]),
            )
        )
    return rows
