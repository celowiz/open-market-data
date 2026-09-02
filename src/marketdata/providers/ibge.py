from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from logging import getLogger

import httpx

from marketdata import __version__
from marketdata.config import get_settings
from marketdata.domain.errors import InvalidFinancialValueError, exact_decimal

SIDRA_BASE = "https://apisidra.ibge.gov.br/values"
# IPCA table 1737: v/63 monthly variation, v/2265 12-month accumulated.
# PIB table 1620 / classification 11255/90707 is a single national volume index.
IBGE_SERIES = (
    (
        "IBGE:IPCA_MOM",
        "1737",
        "63",
        "IPCA variação mensal",
        "percent",
        "/t/1737/n1/all/v/63/p/{period}",
    ),
    (
        "IBGE:IPCA_12M",
        "1737",
        "2265",
        "IPCA variação acumulada em 12 meses",
        "percent",
        "/t/1737/n1/all/v/2265/p/{period}",
    ),
)
logger = getLogger(__name__)


@dataclass(frozen=True)
class IbgeObservation:
    code: str
    source_series_id: str
    name: str
    unit: str
    reference_date: date
    value: Decimal


class IbgeProvider:
    name = "ibge"

    def fetch_series(
        self,
        *,
        code: str,
        table: str,
        variable: str,
        name: str,
        unit: str,
        path_template: str,
        period: str,
        client: httpx.Client | None = None,
    ) -> list[IbgeObservation]:
        settings = get_settings()
        headers = {"User-Agent": f"{settings.http_user_agent}/{__version__}"}
        url = SIDRA_BASE + path_template.format(period=period)
        owns = client is None
        http_client = client or httpx.Client(timeout=settings.http_timeout_seconds, headers=headers)
        try:
            response = http_client.get(url, params={"formato": "json"})
            response.raise_for_status()
            return parse_sidra_observations(
                payload=response.content,
                code=code,
                source_series_id=f"{table}:{variable}",
                name=name,
                unit=unit,
            )
        finally:
            if owns:
                http_client.close()


def parse_sidra_observations(
    *,
    payload: bytes,
    code: str,
    source_series_id: str,
    name: str,
    unit: str,
) -> list[IbgeObservation]:
    import json

    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, list):
        return []
    records: list[IbgeObservation] = []
    for item in data[1:] if data else []:
        if not isinstance(item, dict):
            continue
        raw_value = str(item.get("V") or "").strip()
        period = str(item.get("D3C") or item.get("D2C") or "").strip()
        if not raw_value or raw_value in {"...", "-"}:
            continue
        ref = _sidra_period_to_date(period)
        if ref is None:
            continue
        try:
            records.append(
                IbgeObservation(
                    code=code,
                    source_series_id=source_series_id,
                    name=name,
                    unit=unit,
                    reference_date=ref,
                    value=exact_decimal(raw_value.replace(",", ".")),
                )
            )
        except (InvalidFinancialValueError, InvalidOperation, ValueError):
            continue
    return records


def _sidra_period_to_date(period: str) -> date | None:
    digits = "".join(ch for ch in period if ch.isdigit())
    if len(digits) == 6:
        try:
            return date(int(digits[:4]), int(digits[4:6]), 1)
        except ValueError:
            return None
    if len(digits) == 4:
        try:
            return date(int(digits), 1, 1)
        except ValueError:
            return None
    if len(digits) == 5:
        # YYYYQ where last digit is quarter 1-4, or YYYY + month nibble.
        year = int(digits[:4])
        quarter = int(digits[4])
        if 1 <= quarter <= 4:
            return date(year, 1 + (quarter - 1) * 3, 1)
    return None
