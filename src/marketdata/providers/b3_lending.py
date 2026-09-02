from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from marketdata.domain.errors import InvalidFinancialValueError, exact_decimal
from marketdata.providers.b3 import B3ParseError, _bdi_rows

LENDING_REGISTERED = "registered"
LENDING_OPEN_POSITION = "open_position"

# BDI table export names. Open position is verified against live BDI
# (filings-b3 / Boletim Diário chapter "Securities lending").
# Registered-loan aliases are tried in order; HTTP 400/404 skips that alias.
BDI_OPEN_POSITION_TABLE = "BTBLendingOpenPosition"
BDI_REGISTERED_TABLE_CANDIDATES = (
    "BTBLendingRegistered",
    "BTBRegisteredLending",
    "LoanRegistered",
    "SecuritiesLendingRegistered",
    "BTBLendingSummary",
)

# NEGOCIOSBTB is the negócio-a-negócio tape. Never persist it in Postgres.
# Optional object-store parquet only when OBJECT_STORAGE_BACKEND=s3.
NEGOCIOSBTB_URL_TEMPLATES = (
    (
        "https://arquivos.b3.com.br/api/download/requestname"
        "?fileName=Trade_SecuritiesLending_TradeSecuritiesLendingFile&date={iso}"
    ),
    "https://www.b3.com.br/pesquisapregao/download?filelist={ddmmyyyy}_NEGOCIOSBTB.zip",
)

_TICKER_KEYS = (
    "TCKR_SYMB",
    "TckrSymb",
    "Ticker",
    "TICKER",
    "Codigo",
    "Código",
    "CodNeg",
)
_DATE_KEYS = ("DT_REF", "RptDt", "TradeDate", "Date", "Data", "RPT_DT")
_QTY_KEYS = (
    "STOCK_BALANCE",
    "QTY",
    "Quantity",
    "Quantidade",
    "Qtty",
    "LoanQty",
    "Qtd",
    "Qtde",
    "QtyLoaned",
)
_RATE_KEYS = (
    "AVG_RATE",
    "AverageRate",
    "TaxaMedia",
    "Taxa Média",
    "AvgTax",
    "RATE",
    "Taxa",
    "AvgRate",
)
_CONTRACT_KEYS = (
    "NUM_TRADES",
    "NTrd",
    "Contracts",
    "QtdNegocios",
    "NumberOfTrades",
    "TRADE_COUNT",
    "NContratos",
)
_PRICE_KEYS = ("AVG_PRIC", "AveragePrice", "PrecoMedio", "AvgPric")
_BALANCE_KEYS = ("BALANCE", "Volume", "VlFinanc", "FinancialVolume", "Vl")
_MARKET_KEYS = ("MARKET", "Merc", "Mercado", "Market")


@dataclass(frozen=True)
class B3LendingRecord:
    ticker: str
    reference_date: date
    snapshot_type: str
    qty: Decimal | None
    avg_rate: Decimal | None
    contracts: int | None
    avg_price: Decimal | None
    balance_brl: Decimal | None
    market: str | None
    extra: dict[str, str]


def negociosbtb_urls(reference_date: date) -> tuple[str, ...]:
    iso = reference_date.isoformat()
    ddmmyyyy = reference_date.strftime("%d%m%Y")
    return tuple(
        template.format(iso=iso, ddmmyyyy=ddmmyyyy) for template in NEGOCIOSBTB_URL_TEMPLATES
    )


def _cell(row: dict[str, str], keys: tuple[str, ...]) -> str:
    lowered = {key.lower(): value for key, value in row.items()}
    for key in keys:
        value = row.get(key) or lowered.get(key.lower()) or ""
        if value.strip():
            return value.strip()
    return ""


def _normalize_decimal_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    if text.count(",") == 1 and text.count(".") >= 1:
        return text.replace(".", "").replace(",", ".")
    if text.count(",") == 1 and text.count(".") == 0:
        return text.replace(",", ".")
    return text


def _optional_decimal(raw: str) -> Decimal | None:
    text = _normalize_decimal_text(raw)
    if not text:
        return None
    try:
        return exact_decimal(text)
    except (InvalidFinancialValueError, InvalidOperation, ValueError):
        return None


def _optional_int(raw: str) -> int | None:
    value = _optional_decimal(raw)
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, OverflowError):
        return None


def _parse_date(raw: str, fallback: date) -> date:
    if not raw:
        return fallback
    text = raw.strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    parts = text.replace("/", "-").split("-")
    if len(parts) != 3:
        return fallback
    try:
        if len(parts[0]) == 4:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        return date(int(parts[2]), int(parts[1]), int(parts[0]))
    except ValueError:
        return fallback


def parse_lending_table(
    payload: bytes,
    *,
    snapshot_type: str,
    reference_date: date,
    allowlist: frozenset[str] | None = None,
) -> list[B3LendingRecord]:
    records: list[B3LendingRecord] = []
    seen: set[tuple[str, date, str]] = set()
    for row in _bdi_rows(payload):
        ticker = _cell(row, _TICKER_KEYS).upper()
        if not ticker:
            continue
        if allowlist is not None and ticker not in allowlist:
            continue
        ref = _parse_date(_cell(row, _DATE_KEYS), reference_date)
        key = (ticker, ref, snapshot_type)
        if key in seen:
            continue
        seen.add(key)
        extra = {name: value for name, value in row.items() if value}
        records.append(
            B3LendingRecord(
                ticker=ticker,
                reference_date=ref,
                snapshot_type=snapshot_type,
                qty=_optional_decimal(_cell(row, _QTY_KEYS)),
                avg_rate=_optional_decimal(_cell(row, _RATE_KEYS)),
                contracts=_optional_int(_cell(row, _CONTRACT_KEYS)),
                avg_price=_optional_decimal(_cell(row, _PRICE_KEYS)),
                balance_brl=_optional_decimal(_cell(row, _BALANCE_KEYS)),
                market=_cell(row, _MARKET_KEYS) or None,
                extra=extra,
            )
        )
    return records


def parse_negociosbtb_tape(payload: bytes) -> list[dict[str, str]]:
    """Parse the BTB tape for optional parquet only. Never persist rows in Postgres."""
    blobs: list[bytes]
    if payload[:2] == b"PK":
        try:
            archive = ZipFile(BytesIO(payload))
        except BadZipFile as exc:
            raise B3ParseError("invalid NEGOCIOSBTB ZIP") from exc
        with archive:
            blobs = [archive.read(name) for name in archive.namelist()]
    else:
        blobs = [payload]
    rows: list[dict[str, str]] = []
    for blob in blobs:
        if blob:
            rows.extend(_bdi_rows(blob))
    return rows
