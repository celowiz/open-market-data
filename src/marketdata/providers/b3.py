from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

import httpx

from marketdata import __version__
from marketdata.config import get_settings
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
class B3InstrumentRecord:
    ticker: str
    isin: str | None
    name: str | None
    currency: str | None


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


def iter_xml_blobs(payload: bytes) -> list[bytes]:
    validate_b3_zip(payload)
    blobs: list[bytes] = []
    _collect_xml_blobs(payload, blobs)
    if not blobs:
        raise B3ParseError("ZIP does not contain XML")
    return blobs


def _collect_xml_blobs(payload: bytes, blobs: list[bytes]) -> None:
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
                _collect_xml_blobs(data, blobs)
                continue
            stripped = data.lstrip()
            if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
                blobs.append(data)


def parse_price_report(payload: bytes) -> list[B3PriceRecord]:
    records: list[B3PriceRecord] = []
    for blob in iter_xml_blobs(payload):
        records.extend(_parse_price_xml(blob))
    return records


def parse_instrument_master(payload: bytes) -> dict[str, B3InstrumentRecord]:
    by_ticker: dict[str, B3InstrumentRecord] = {}
    for blob in iter_xml_blobs(payload):
        by_ticker.update(_parse_master_xml(blob))
    return by_ticker


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


def _parse_master_xml(blob: bytes) -> dict[str, B3InstrumentRecord]:
    by_ticker: dict[str, B3InstrumentRecord] = {}
    for _event, elem in ET.iterparse(BytesIO(blob), events=("end",)):
        if _local_name(elem.tag) != "EqtyInf":
            continue
        ticker = _child_text(elem, "TckrSymb") or _text(elem, "TckrSymb")
        if not ticker:
            elem.clear()
            continue
        by_ticker[ticker] = B3InstrumentRecord(
            ticker=ticker,
            isin=_child_text(elem, "ISIN") or _text(elem, "ISIN"),
            name=_child_text(elem, "CrpnNm") or _text(elem, "CrpnNm"),
            currency=_child_text(elem, "TradgCcy") or _text(elem, "TradgCcy"),
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
        timeout = max(settings.http_timeout_seconds, 120)
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
