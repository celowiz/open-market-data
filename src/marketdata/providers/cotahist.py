"""COTAHIST annual equity history. Not BVBG.186 and never official settlement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import BadZipFile, ZipFile

import httpx

from marketdata import __version__
from marketdata.config import get_settings
from marketdata.domain.enums import PriceType
from marketdata.domain.errors import InvalidFinancialValueError, exact_decimal

COTAHIST_HOST = "bvmf.bmfbovespa.com.br"
COTAHIST_PATH = "/InstDados/SerHist/COTAHIST_A{year}.ZIP"


class CotahistParseError(ValueError):
    """Raised when a COTAHIST annual payload cannot be parsed."""


@dataclass(frozen=True)
class CotahistQuoteRecord:
    ticker: str
    reference_date: date
    last_price: Decimal
    currency: str
    isin: str | None
    extra: dict[str, str]
    price_type: PriceType = PriceType.LAST


def cotahist_year_url(year: int, *, https: bool = False) -> str:
    scheme = "https" if https else "http"
    return f"{scheme}://{COTAHIST_HOST}{COTAHIST_PATH.format(year=year)}"


def _slice(line: str, start: int, end: int) -> str:
    return line[start - 1 : end]


def implied_decimal_2(raw: str) -> Decimal:
    """Parse an N(11)V99 COTAHIST price field without binary floats."""
    digits = raw.strip()
    if not digits or not digits.isdigit():
        raise InvalidFinancialValueError("COTAHIST price field is not numeric")
    if set(digits) == {"0"}:
        raise InvalidFinancialValueError("COTAHIST price field is zero")
    padded = digits.zfill(3)
    return exact_decimal(f"{padded[:-2]}.{padded[-2:]}")


def _parse_quote_line(line: str) -> CotahistQuoteRecord | None:
    ticker = _slice(line, 13, 24).strip()
    raw_date = _slice(line, 3, 10)
    if not ticker or len(raw_date) != 8:
        return None
    try:
        reference_date = date(int(raw_date[0:4]), int(raw_date[4:6]), int(raw_date[6:8]))
    except ValueError:
        return None
    try:
        last_price = implied_decimal_2(_slice(line, 109, 121))
    except (InvalidFinancialValueError, InvalidOperation, ValueError):
        return None
    isin = _slice(line, 231, 242).strip() if len(line) >= 242 else ""
    extra = {
        "origin": "COTAHIST",
        "source_field": "PREULT",
        "source_file": "COTAHIST",
    }
    if len(line) >= 12:
        extra["CODBDI"] = _slice(line, 11, 12).strip()
    if len(line) >= 27:
        extra["TPMERC"] = _slice(line, 25, 27).strip()
    if len(line) >= 56:
        extra["MODREF"] = _slice(line, 53, 56).strip()
    if len(line) >= 202:
        extra["INDOPC"] = _slice(line, 202, 202)
    extra = {key: value for key, value in extra.items() if value}
    return CotahistQuoteRecord(
        ticker=ticker,
        reference_date=reference_date,
        last_price=last_price,
        currency="BRL",
        isin=isin or None,
        extra=extra,
        price_type=PriceType.LAST,
    )


def parse_cotahist(text: str) -> list[CotahistQuoteRecord]:
    """Parse COTAHIST fixed-width text. Only register type 01 is a quote."""
    records: list[CotahistQuoteRecord] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if len(line) < 121:
            continue
        if _slice(line, 1, 2) != "01":
            continue
        parsed = _parse_quote_line(line)
        if parsed is not None:
            records.append(parsed)
    return records


def parse_cotahist_zip(payload: bytes) -> list[CotahistQuoteRecord]:
    try:
        archive = ZipFile(BytesIO(payload))
    except BadZipFile as exc:
        raise CotahistParseError("COTAHIST payload is not a usable ZIP") from exc
    with archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if not names:
            raise CotahistParseError("COTAHIST ZIP is empty")
        chosen = next((name for name in names if name.upper().endswith(".TXT")), names[0])
        text = archive.read(chosen).decode("latin-1")
    return parse_cotahist(text)


def fetch_cotahist_year(year: int, *, client: httpx.Client | None = None) -> httpx.Response:
    """Download COTAHIST_A{YYYY}.ZIP, trying HTTP then HTTPS."""
    settings = get_settings()
    headers = {"User-Agent": f"{settings.http_user_agent}/{__version__}"}
    timeout = max(settings.http_timeout_seconds, 120)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout, follow_redirects=True, headers=headers)
    errors: list[BaseException] = []
    try:
        for https in (False, True):
            url = cotahist_year_url(year, https=https)
            try:
                response = http_client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                errors.append(exc)
                continue
            if response.content[:2] == b"PK":
                return response
            errors.append(CotahistParseError(f"COTAHIST response is not a ZIP: {url}"))
        if errors:
            raise errors[-1]
        raise CotahistParseError(f"COTAHIST_A{year}.ZIP could not be downloaded")
    finally:
        if owns_client:
            http_client.close()
