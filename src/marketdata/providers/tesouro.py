from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import httpx

from marketdata import __version__
from marketdata.config import get_settings
from marketdata.domain.enums import PriceType
from marketdata.domain.errors import exact_decimal

TITLE_TYPE_BY_NAME = {
    "Tesouro Selic": "LFT",
    "Tesouro Prefixado": "LTN",
    "Tesouro Prefixado com Juros Semestrais": "NTN-F",
    "Tesouro IPCA+": "NTN-B Principal",
    "Tesouro IPCA+ com Juros Semestrais": "NTN-B",
    "Tesouro IGPM+ com Juros Semestrais": "NTN-C",
    "Tesouro Renda+": "NTN-B1",
    "Tesouro Educa+": "NTN-B1",
}

TESOURO_CSV_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)

FIELD_PRICE_TYPES = (
    ("PU Base Manha", PriceType.PU_BASE, "BRL"),
    ("PU Compra Manha", PriceType.BID_PU, "BRL"),
    ("PU Venda Manha", PriceType.ASK_PU, "BRL"),
    ("Taxa Compra Manha", PriceType.YIELD, "percent_per_year"),
    ("Taxa Venda Manha", PriceType.INDICATIVE, "percent_per_year"),
)


@dataclass(frozen=True)
class TesouroQuoteRecord:
    title_type: str
    marketing_name: str
    maturity_date: date
    reference_date: date
    value: Decimal
    price_type: PriceType
    unit: str
    source_field: str


def parse_brazilian_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%d/%m/%Y").date()


def parse_brazilian_decimal(value: str) -> Decimal:
    cleaned = value.strip().replace(".", "").replace(",", ".")
    return exact_decimal(cleaned)


def map_title_type(name: str) -> str:
    return TITLE_TYPE_BY_NAME.get(name, name)


def tesouro_instrument_key(title_type: str, maturity: date) -> str:
    return f"{title_type}:{maturity.isoformat()}"


def tesouro_record_key(record: TesouroQuoteRecord) -> str:
    return tesouro_instrument_key(record.title_type, record.maturity_date)


def current_tesouro_title_keys(records: list[TesouroQuoteRecord]) -> set[str]:
    """Instrument keys present on the latest Data Base date in `records`."""
    if not records:
        return set()
    latest = max(record.reference_date for record in records)
    return {tesouro_record_key(record) for record in records if record.reference_date == latest}


def filter_current_tesouro_titles(records: list[TesouroQuoteRecord]) -> list[TesouroQuoteRecord]:
    """Keep full history of titles that appear on the latest Data Base date.

    Rows whose identity is absent from that latest-day set (matured / off-book)
    are dropped. The latest day is taken from the records passed in, which
    should be the full CKAN CSV so a date-windowed backfill still uses today's
    traded set.
    """
    keys = current_tesouro_title_keys(records)
    return [record for record in records if tesouro_record_key(record) in keys]


def parse_tesouro_csv(text: str, *, reference_date: date | None = None) -> list[TesouroQuoteRecord]:
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    records: list[TesouroQuoteRecord] = []
    for row in reader:
        normalized = {key.strip(): (value or "").strip() for key, value in row.items() if key}
        name = normalized.get("Tipo Titulo") or normalized.get("Tipo Título") or ""
        if not name:
            continue
        maturity = parse_brazilian_date(normalized["Data Vencimento"])
        base = parse_brazilian_date(normalized["Data Base"])
        if reference_date is not None and base != reference_date:
            continue
        title_type = map_title_type(name)
        for field, price_type, unit in FIELD_PRICE_TYPES:
            raw = normalized.get(field, "")
            if not raw:
                continue
            records.append(
                TesouroQuoteRecord(
                    title_type=title_type,
                    marketing_name=name,
                    maturity_date=maturity,
                    reference_date=base,
                    value=parse_brazilian_decimal(raw),
                    price_type=price_type,
                    unit=unit,
                    source_field=field,
                )
            )
    return records


class TesouroProvider:
    name = "tesouro"

    def csv_url(self) -> str:
        return TESOURO_CSV_URL

    def fetch_csv(self, *, client: httpx.Client | None = None) -> httpx.Response:
        settings = get_settings()
        headers = {"User-Agent": f"{settings.http_user_agent}/{__version__}"}
        owns_client = client is None
        http_client = client or httpx.Client(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            headers=headers,
        )
        try:
            response = http_client.get(self.csv_url())
            response.raise_for_status()
            return response
        finally:
            if owns_client:
                http_client.close()
