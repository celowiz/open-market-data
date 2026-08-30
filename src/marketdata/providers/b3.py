from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

import httpx

from marketdata import __version__
from marketdata.config import Settings, get_settings
from marketdata.domain.errors import InvalidFinancialValueError, exact_decimal

PREGAO_DOWNLOAD = "https://www.b3.com.br/pesquisapregao/download?filelist={filelist}"
FILELIST_BY_KIND = {
    "186": ("SPRE", ".zip"),
    "187": ("SPRD", ".zip"),
    "028": ("IN", ".zip"),
    "086": ("PR", ".zip"),
    "087": ("IR", ".zip"),
}
MIN_ZIP_BYTES = 100
FUTURE_TICKER_RE = re.compile(r"^(DI1|DOL|WDO|WIN|IND)[FGHJKMNQUVXZ]\d{2}$")
BDI_EXPORT_URL = "https://arquivos.b3.com.br/bdi/table/export"
BDI_CREDIT_TRADES_TABLE = "ConsolidatedRecords"
BDI_CREDIT_MASTER_TABLE = "InstrumentRegistration"
CREDIT_TYPE_MAP = {
    "DEB": "debenture",
    "CRI": "cri",
    "CRI PÚBLICO": "cri",
    "CRI PUBLICO": "cri",
    "CRA": "cra",
    "CRA PÚBLICO": "cra",
    "CRA PUBLICO": "cra",
}


def is_mvp_future_ticker(ticker: str) -> bool:
    return FUTURE_TICKER_RE.fullmatch(ticker) is not None


class B3ParseError(ValueError):
    """Raised when a B3 Pesquisa por Pregão payload cannot be used."""


@dataclass(frozen=True)
class B3PriceRecord:
    ticker: str
    reference_date: date
    last_price: Decimal
    security_id: str | None
    currency: str | None
    extra: dict[str, str]


@dataclass(frozen=True)
class B3SettlementRecord:
    ticker: str
    reference_date: date
    settlement: Decimal
    unit: str
    security_id: str | None
    currency: str | None
    extra: dict[str, str]


@dataclass(frozen=True)
class B3InstrumentRecord:
    ticker: str
    isin: str | None
    name: str | None
    currency: str | None
    maturity_date: date | None = None


@dataclass(frozen=True)
class B3CreditTradeRecord:
    ticker: str
    reference_date: date
    last_price: Decimal
    instrument_type: str
    isin: str | None
    name: str | None
    extra: dict[str, str]


@dataclass(frozen=True)
class B3CreditInstrumentRecord:
    ticker: str
    instrument_type: str
    isin: str | None
    name: str | None
    maturity_date: date | None = None


def pregao_filelist(kind: str, reference_date: date) -> str:
    try:
        prefix, suffix = FILELIST_BY_KIND[kind]
    except KeyError as exc:
        raise B3ParseError(f"unknown B3 file kind: {kind}") from exc
    return f"{prefix}{reference_date.strftime('%y%m%d')}{suffix}"


def pregao_url(kind: str, reference_date: date) -> str:
    return PREGAO_DOWNLOAD.format(filelist=pregao_filelist(kind, reference_date))


def validate_b3_zip(payload: bytes) -> None:
    if len(payload) < MIN_ZIP_BYTES or payload[:4] != b"PK\x03\x04":
        raise B3ParseError("B3 response is not a usable ZIP")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def b3_http_timeout(settings: Settings | None = None) -> httpx.Timeout:
    """Bounded client timeout so Pesquisa por Pregão / BDI cannot run to the job cap.

    `read` is per-chunk idle time, not total download time. Connect is short so a
    hung handshake fails in seconds instead of 2 hours of silence.
    """
    cfg = settings if settings is not None else get_settings()
    read = max(float(cfg.http_timeout_seconds), 60.0)
    return httpx.Timeout(connect=15.0, read=read, write=30.0, pool=15.0)


def iter_xml_blobs(payload: bytes) -> Iterator[bytes]:
    """Yield inner XML documents one at a time (do not hold a 028-sized pair in RAM)."""
    validate_b3_zip(payload)
    yielded = False
    for blob in _yield_xml_blobs(payload):
        yielded = True
        yield blob
    if not yielded:
        raise B3ParseError("ZIP does not contain XML")


def _yield_xml_blobs(payload: bytes) -> Iterator[bytes]:
    try:
        archive = ZipFile(BytesIO(payload))
    except BadZipFile as exc:
        raise B3ParseError("invalid ZIP archive") from exc
    with archive:
        names = archive.namelist()
        if not names:
            raise B3ParseError("ZIP is empty")
        for name in names:
            data = archive.read(name)
            if data[:4] == b"PK\x03\x04" and len(data) >= MIN_ZIP_BYTES:
                yield from _yield_xml_blobs(data)
                continue
            stripped = data.lstrip()
            if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
                yield data


def parse_price_report(payload: bytes) -> list[B3PriceRecord]:
    records: list[B3PriceRecord] = []
    for blob in iter_xml_blobs(payload):
        records.extend(_parse_price_xml(blob))
    return records


def parse_settlement_report(payload: bytes) -> list[B3SettlementRecord]:
    by_key: dict[tuple[str, date], B3SettlementRecord] = {}
    for blob in iter_xml_blobs(payload):
        for record in _parse_settlement_xml(blob):
            by_key[(record.ticker, record.reference_date)] = record
    return list(by_key.values())


def parse_instrument_master(
    payload: bytes, *, keep_tickers: frozenset[str] | None = None
) -> dict[str, B3InstrumentRecord]:
    by_ticker: dict[str, B3InstrumentRecord] = {}
    # Inner IN zip often has two near-duplicate XML files (~0.6GB each). Parse the
    # first only; the second is not worth a second full document walk.
    for blob in iter_xml_blobs(payload):
        by_ticker.update(_parse_master_xml(blob, keep_tickers=keep_tickers))
        break
    return by_ticker


def credit_instrument_type(code: str | None) -> str | None:
    if not code:
        return None
    return CREDIT_TYPE_MAP.get(code.strip().upper())


def parse_otc_trade_file(payload: bytes) -> list[B3CreditTradeRecord]:
    by_key: dict[tuple[str, date], B3CreditTradeRecord] = {}
    for row in _bdi_rows(payload):
        parsed = _credit_trade_from_row(row)
        if parsed is None:
            continue
        key = (parsed.ticker, parsed.reference_date)
        existing = by_key.get(key)
        if existing is None or (
            existing.extra.get("BusinessClass") != "EXTRAGRUPO"
            and parsed.extra.get("BusinessClass") == "EXTRAGRUPO"
        ):
            by_key[key] = parsed
    return list(by_key.values())


def otc_payload_has_rows(payload: bytes) -> bool:
    try:
        return bool(_bdi_rows(payload))
    except (B3ParseError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return False


def otc_payload_report_date(payload: bytes) -> date | None:
    try:
        rows = _bdi_rows(payload)
    except (B3ParseError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
    for row in rows:
        parsed = _parse_iso_date(row.get("TradeDate") or row.get("RptDt") or row.get("DtRef") or "")
        if parsed is not None:
            return parsed
    return None


def parse_otc_instrument_file(payload: bytes) -> list[B3CreditInstrumentRecord]:
    records: list[B3CreditInstrumentRecord] = []
    seen: set[str] = set()
    for row in _bdi_rows(payload):
        parsed = _credit_instrument_from_row(row)
        if parsed is None or parsed.ticker in seen:
            continue
        seen.add(parsed.ticker)
        records.append(parsed)
    return records


def _bdi_rows(payload: bytes) -> list[dict[str, str]]:
    stripped = payload.lstrip()
    if not stripped:
        return []
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        return _rows_from_json(payload)
    return _rows_from_csv(payload)


def _rows_from_json(payload: bytes) -> list[dict[str, str]]:
    data = json.loads(payload, parse_float=str, parse_int=str)
    if isinstance(data, list):
        return [
            {str(key): _cell(value) for key, value in item.items()}
            for item in data
            if isinstance(item, dict)
        ]
    if not isinstance(data, dict):
        raise B3ParseError("BDI payload is not a JSON object")
    columns = data.get("columns") or []
    names = [str(column.get("name") or "") for column in columns]
    rows: list[dict[str, str]] = []
    for raw in data.get("values") or []:
        if not isinstance(raw, list):
            continue
        mapped: dict[str, str] = {}
        for index, name in enumerate(names):
            if not name:
                continue
            mapped[name] = _cell(raw[index] if index < len(raw) else None)
        rows.append(mapped)
    return rows


def _rows_from_csv(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig")
    sample = text[:1024]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    return [{str(key): _cell(value) for key, value in row.items() if key} for row in reader]


def _cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "null"}:
        return ""
    return text


def _parse_iso_date(raw: str) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _credit_trade_from_row(row: dict[str, str]) -> B3CreditTradeRecord | None:
    instrument_type = credit_instrument_type(row.get("InstrumentCode") or row.get("InstrumentType"))
    ticker = row.get("TckrSymb") or ""
    raw_date = row.get("TradeDate") or row.get("RptDt") or ""
    last_raw = row.get("Closing") or ""
    trades_raw = row.get("NumberOfTrades")
    qty_raw = row.get("Quantity")
    if not instrument_type or not ticker or not last_raw:
        return None
    activity_raw = trades_raw or qty_raw or "0"
    try:
        trade_count = int(Decimal(activity_raw)) if activity_raw else 0
    except (InvalidOperation, ValueError):
        return None
    if trade_count <= 0:
        return None
    try:
        last_price = exact_decimal(last_raw)
    except (InvalidFinancialValueError, InvalidOperation, ValueError):
        return None
    reference_date = _parse_iso_date(raw_date)
    if reference_date is None:
        return None
    extra_fields = (
        "Minimum",
        "Maximum",
        "Average",
        "Quantity",
        "Volume",
        "NumberOfTrades",
        "BusinessClass",
        "ReferencePrice",
        "SettlementDt",
        "Osc",
    )
    extra = {field: row[field] for field in extra_fields if row.get(field)}
    extra["source_field"] = "Closing"
    return B3CreditTradeRecord(
        ticker=ticker,
        reference_date=reference_date,
        last_price=last_price,
        instrument_type=instrument_type,
        isin=row.get("ISIN") or None,
        name=row.get("Issuer") or ticker,
        extra=extra,
    )


def _credit_instrument_from_row(row: dict[str, str]) -> B3CreditInstrumentRecord | None:
    instrument_type = credit_instrument_type(row.get("InstrumentType") or row.get("InstrumentCode"))
    ticker = row.get("TckrSymb") or ""
    if not instrument_type or not ticker:
        return None
    return B3CreditInstrumentRecord(
        ticker=ticker,
        instrument_type=instrument_type,
        isin=row.get("ISIN") or None,
        name=row.get("Issuer") or ticker,
        maturity_date=_parse_iso_date(row.get("Maturity") or ""),
    )


def _parse_price_xml(blob: bytes) -> list[B3PriceRecord]:
    records: list[B3PriceRecord] = []
    for _event, elem in ET.iterparse(BytesIO(blob), events=("end",)):
        if _local_name(elem.tag) != "PricRpt":
            continue
        parsed = _price_from_element(elem)
        if parsed is not None:
            records.append(parsed)
        elem.clear()
    return records


def _text(elem: ET.Element, name: str) -> str | None:
    for child in elem.iter():
        if _local_name(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _child_text(parent: ET.Element, name: str) -> str | None:
    for child in parent:
        if _local_name(child.tag) == name:
            if child.text and child.text.strip():
                return child.text.strip()
            return None
    return None


def _attrs_element(elem: ET.Element) -> ET.Element | None:
    for child in elem:
        if _local_name(child.tag) == "FinInstrmAttrbts":
            return child
    return None


SETTLEMENT_EXTRA_FIELDS = (
    "AdjstdQtTax",
    "PrvsAdjstdQt",
    "PrvsAdjstdQtTax",
    "OpnIntrst",
    "LastPric",
)


def _ccy_from_child(attrs: ET.Element, name: str) -> str | None:
    child = next((item for item in attrs if _local_name(item.tag) == name), None)
    if child is None:
        return None
    return child.attrib.get("Ccy")


def _parse_settlement_xml(blob: bytes) -> list[B3SettlementRecord]:
    records: list[B3SettlementRecord] = []
    for _event, elem in ET.iterparse(BytesIO(blob), events=("end",)):
        if _local_name(elem.tag) != "PricRpt":
            continue
        parsed = _settlement_from_element(elem)
        if parsed is not None:
            records.append(parsed)
        elem.clear()
    return records


def _settlement_from_element(elem: ET.Element) -> B3SettlementRecord | None:
    ticker = _text(elem, "TckrSymb")
    raw_date = _text(elem, "Dt")
    attrs = _attrs_element(elem)
    if not ticker or not raw_date or attrs is None:
        return None
    adj_raw = _child_text(attrs, "AdjstdQt")
    tax_raw = _child_text(attrs, "AdjstdQtTax")
    if adj_raw:
        raw_value, unit, currency_field = adj_raw, "PU", "AdjstdQt"
    elif tax_raw:
        raw_value, unit, currency_field = tax_raw, "percent_per_year", "AdjstdQtTax"
    else:
        return None
    try:
        settlement = exact_decimal(raw_value)
    except (InvalidFinancialValueError, InvalidOperation, ValueError):
        return None
    extra: dict[str, str] = {}
    for field in SETTLEMENT_EXTRA_FIELDS:
        value = _child_text(attrs, field)
        if value is not None:
            extra[field] = value
    if tax_raw is not None:
        extra["rate_convention"] = "252_business_days"
    return B3SettlementRecord(
        ticker=ticker,
        reference_date=date.fromisoformat(raw_date),
        settlement=settlement,
        unit=unit,
        security_id=_text(elem, "Id") if _text(elem, "Id") != ticker else None,
        currency=_ccy_from_child(attrs, currency_field),
        extra=extra,
    )


def _price_from_element(elem: ET.Element) -> B3PriceRecord | None:
    ticker = _text(elem, "TckrSymb")
    raw_date = _text(elem, "Dt")
    attrs = _attrs_element(elem)
    last_raw = _child_text(attrs, "LastPric") if attrs is not None else None
    if not ticker or not raw_date or not last_raw:
        return None
    try:
        last_price = exact_decimal(last_raw)
    except (InvalidFinancialValueError, InvalidOperation, ValueError):
        return None
    currency = None
    extra: dict[str, str] = {}
    if attrs is not None:
        last_elem = next((child for child in attrs if _local_name(child.tag) == "LastPric"), None)
        if last_elem is not None:
            currency = last_elem.attrib.get("Ccy")
        for field in ("FrstPric", "MinPric", "MaxPric", "TradAvrgPric", "RglrTxsQty"):
            value = _child_text(attrs, field)
            if value is not None:
                extra[field] = value
    return B3PriceRecord(
        ticker=ticker,
        reference_date=date.fromisoformat(raw_date),
        last_price=last_price,
        security_id=_text(elem, "Id") if _text(elem, "Id") != ticker else None,
        currency=currency,
        extra=extra,
    )


_MASTER_BLOCKS = frozenset({"EqtyInf", "FutrCtrctsInf"})


def _parse_master_xml(
    blob: bytes, keep_tickers: frozenset[str] | None = None
) -> dict[str, B3InstrumentRecord]:
    by_ticker: dict[str, B3InstrumentRecord] = {}
    for _event, elem in ET.iterparse(BytesIO(blob), events=("end",)):
        block = _local_name(elem.tag)
        if block not in _MASTER_BLOCKS:
            continue
        ticker = _child_text(elem, "TckrSymb") or _text(elem, "TckrSymb")
        if not ticker:
            elem.clear()
            continue
        if keep_tickers is not None and ticker not in keep_tickers:
            elem.clear()
            continue
        raw_maturity = _child_text(elem, "XprtnDt") or _text(elem, "XprtnDt")
        maturity = date.fromisoformat(raw_maturity) if raw_maturity else None
        by_ticker[ticker] = B3InstrumentRecord(
            ticker=ticker,
            isin=_child_text(elem, "ISIN") or _text(elem, "ISIN"),
            name=_child_text(elem, "CrpnNm") or _text(elem, "CrpnNm") or ticker,
            currency=_child_text(elem, "TradgCcy") or _text(elem, "TradgCcy"),
            maturity_date=maturity,
        )
        elem.clear()
    return by_ticker


class B3Provider:
    name = "b3"

    def fetch(
        self, kind: str, reference_date: date, *, client: httpx.Client | None = None
    ) -> httpx.Response:
        settings = get_settings()
        headers = {"User-Agent": f"{settings.http_user_agent}/{__version__}"}
        timeout = b3_http_timeout(settings)
        owns_client = client is None
        http_client = client or httpx.Client(
            timeout=timeout, follow_redirects=True, headers=headers
        )
        url = pregao_url(kind, reference_date)
        try:
            response = http_client.get(url)
            response.raise_for_status()
            validate_b3_zip(response.content)
            return response
        finally:
            if owns_client:
                http_client.close()

    def fetch_public_table(
        self, table_name: str, reference_date: date, *, client: httpx.Client | None = None
    ) -> httpx.Response:
        settings = get_settings()
        headers = {"User-Agent": f"{settings.http_user_agent}/{__version__}"}
        timeout = b3_http_timeout(settings)
        owns_client = client is None
        http_client = client or httpx.Client(
            timeout=timeout, follow_redirects=True, headers=headers
        )
        try:
            response = http_client.post(
                BDI_EXPORT_URL,
                json={
                    "Name": table_name,
                    "Date": reference_date.isoformat(),
                    "FinalDate": reference_date.isoformat(),
                    "ClientId": "",
                    "Filters": None,
                },
            )
            response.raise_for_status()
            if not response.content.strip():
                raise B3ParseError(f"BDI table {table_name} returned an empty payload")
            return response
        finally:
            if owns_client:
                http_client.close()
