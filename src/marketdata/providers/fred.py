from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from logging import getLogger

import httpx

from marketdata import __version__
from marketdata.config import Settings, get_settings
from marketdata.domain.errors import InvalidFinancialValueError, exact_decimal

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
logger = getLogger(__name__)


@dataclass(frozen=True)
class FredObservation:
    series_id: str
    reference_date: date
    value: Decimal


class FredProvider:
    name = "fred"

    def fetch_observations(
        self,
        series_id: str,
        *,
        api_key: str,
        start: date,
        end: date,
        client: httpx.Client | None = None,
    ) -> list[FredObservation]:
        settings = get_settings()
        headers = {"User-Agent": f"{settings.http_user_agent}/{__version__}"}
        owns = client is None
        http_client = client or httpx.Client(timeout=settings.http_timeout_seconds, headers=headers)
        try:
            response = http_client.get(
                FRED_OBSERVATIONS_URL,
                params={
                    "series_id": series_id,
                    "api_key": api_key,
                    "file_type": "json",
                    "observation_start": start.isoformat(),
                    "observation_end": end.isoformat(),
                },
            )
            response.raise_for_status()
            return parse_fred_observations(series_id, response.content)
        finally:
            if owns:
                http_client.close()


def parse_fred_observations(series_id: str, payload: bytes) -> list[FredObservation]:
    import json

    data = json.loads(payload.decode("utf-8"))
    rows = data.get("observations") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    records: list[FredObservation] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        raw_date = str(item.get("date") or "")
        raw_value = str(item.get("value") or "").strip()
        if not raw_date or raw_value in {"", "."}:
            continue
        try:
            records.append(
                FredObservation(
                    series_id=series_id,
                    reference_date=date.fromisoformat(raw_date[:10]),
                    value=exact_decimal(raw_value),
                )
            )
        except (InvalidFinancialValueError, InvalidOperation, ValueError):
            continue
    return records


def fred_http_timeout(settings: Settings | None = None) -> httpx.Timeout:
    cfg = settings if settings is not None else get_settings()
    return httpx.Timeout(connect=15.0, read=max(float(cfg.http_timeout_seconds), 30.0))
