from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from logging import getLogger
from xml.etree import ElementTree as ET

import httpx

from marketdata import __version__
from marketdata.config import get_settings
from marketdata.domain.errors import InvalidFinancialValueError, exact_decimal
from marketdata.ingestion.config_tables import load_scratch_cusip_map

SEC_CURRENT_13F_ATOM = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type=13F-HR&count=20&output=atom"
)
logger = getLogger(__name__)


@dataclass(frozen=True)
class ThirteenFHolding:
    filer_cik: str
    filer_name: str
    report_date: date
    cusip: str
    ticker: str
    shares: Decimal | None
    value_usd: Decimal | None


class EdgarProvider:
    name = "edgar"

    def fetch_latest_holdings(
        self,
        *,
        cusip_map: dict[str, str] | None = None,
        client: httpx.Client | None = None,
        atom_payload: bytes | None = None,
        information_tables: list[tuple[str, str, date, bytes]] | None = None,
    ) -> list[ThirteenFHolding]:
        mapping = cusip_map if cusip_map is not None else load_scratch_cusip_map()
        if not mapping:
            logger.info("13F skipped: scratch CUSIP map is empty")
            return []
        if information_tables is not None:
            holdings: list[ThirteenFHolding] = []
            for cik, name, report_date, payload in information_tables:
                holdings.extend(
                    parse_13f_information_table(
                        payload,
                        filer_cik=cik,
                        filer_name=name,
                        report_date=report_date,
                        cusip_map=mapping,
                    )
                )
            return holdings
        _ = atom_payload, client
        # Live path is best-effort: atom + a handful of latest filings.
        return self._fetch_live(mapping, client=client)

    def _fetch_live(
        self,
        mapping: dict[str, str],
        *,
        client: httpx.Client | None,
    ) -> list[ThirteenFHolding]:
        settings = get_settings()
        headers = {
            "User-Agent": f"{settings.http_user_agent}/{__version__} open-market-data",
            "Accept": "application/atom+xml,application/xml,text/xml,*/*",
        }
        owns = client is None
        http_client = client or httpx.Client(timeout=settings.http_timeout_seconds, headers=headers)
        try:
            response = http_client.get(SEC_CURRENT_13F_ATOM)
            response.raise_for_status()
            filings = parse_13f_atom(response.content)
            holdings: list[ThirteenFHolding] = []
            for filing in filings[:10]:
                table_url = filing.get("href")
                if not table_url:
                    continue
                try:
                    table = http_client.get(table_url)
                    table.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.info("13F skip filing url=%s error=%s", table_url, type(exc).__name__)
                    continue
                holdings.extend(
                    parse_13f_information_table(
                        table.content,
                        filer_cik=filing["cik"],
                        filer_name=filing["name"],
                        report_date=filing["report_date"],
                        cusip_map=mapping,
                    )
                )
            return holdings
        finally:
            if owns:
                http_client.close()


def parse_13f_atom(payload: bytes) -> list[dict[str, object]]:
    root = ET.fromstring(payload)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    filings: list[dict[str, object]] = []
    for entry in root.findall("atom:entry", ns) or root.findall("entry"):
        title = (entry.findtext("atom:title", default="", namespaces=ns) or entry.findtext("title") or "")
        link = entry.find("atom:link", ns)
        if link is None:
            link = entry.find("link")
        href = link.get("href") if link is not None else ""
        updated = (
            entry.findtext("atom:updated", default="", namespaces=ns) or entry.findtext("updated") or ""
        )
        try:
            report_date = date.fromisoformat(updated[:10])
        except ValueError:
            continue
        cik = "".join(ch for ch in title if ch.isdigit())[:10] or "0"
        filings.append(
            {
                "name": title.split("(")[0].strip() or "unknown",
                "cik": cik.zfill(10),
                "href": href,
                "report_date": report_date,
            }
        )
    return filings


def parse_13f_information_table(
    payload: bytes,
    *,
    filer_cik: str,
    filer_name: str,
    report_date: date,
    cusip_map: dict[str, str],
) -> list[ThirteenFHolding]:
    text = payload.decode("utf-8", errors="replace")
    if "<" in text[:200]:
        return _parse_13f_xml(payload, filer_cik, filer_name, report_date, cusip_map)
    return _parse_13f_text(text, filer_cik, filer_name, report_date, cusip_map)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _parse_13f_xml(
    payload: bytes,
    filer_cik: str,
    filer_name: str,
    report_date: date,
    cusip_map: dict[str, str],
) -> list[ThirteenFHolding]:
    root = ET.fromstring(payload)
    holdings: list[ThirteenFHolding] = []
    for elem in root.iter():
        if _local(elem.tag) != "infotable":
            continue
        fields: dict[str, str] = {}
        for child in elem.iter():
            name = _local(child.tag)
            text = (child.text or "").strip()
            if text:
                fields[name] = text
        cusip = fields.get("cusip", "").upper()
        ticker = cusip_map.get(cusip)
        if not ticker:
            continue
        holdings.append(
            ThirteenFHolding(
                filer_cik=filer_cik,
                filer_name=filer_name,
                report_date=report_date,
                cusip=cusip,
                ticker=ticker,
                shares=_maybe_decimal(fields.get("sshprnamt") or fields.get("shrsorprnamt")),
                value_usd=_maybe_decimal(fields.get("value")),
            )
        )
    return holdings


def _parse_13f_text(
    text: str,
    filer_cik: str,
    filer_name: str,
    report_date: date,
    cusip_map: dict[str, str],
) -> list[ThirteenFHolding]:
    holdings: list[ThirteenFHolding] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if len(line) < 9:
            continue
        for cusip, ticker in cusip_map.items():
            if cusip and cusip in line.upper():
                holdings.append(
                    ThirteenFHolding(
                        filer_cik=filer_cik,
                        filer_name=filer_name,
                        report_date=report_date,
                        cusip=cusip,
                        ticker=ticker,
                        shares=None,
                        value_usd=None,
                    )
                )
                break
    return holdings


def _maybe_decimal(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    text = raw.strip().replace(",", "")
    if not text:
        return None
    try:
        return exact_decimal(text)
    except (InvalidFinancialValueError, InvalidOperation, ValueError):
        return None
