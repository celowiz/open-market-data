from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from logging import getLogger

import httpx

from marketdata import __version__
from marketdata.config import get_settings
from marketdata.domain.errors import InvalidFinancialValueError, exact_decimal
from marketdata.ingestion.config_tables import CotContractSpec, load_cot_contracts

# Disaggregated futures-only (commodities) and TFF futures-only (financials).
CFTC_DISAGGREGATED_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
CFTC_TFF_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
logger = getLogger(__name__)


@dataclass(frozen=True)
class CotRecord:
    contract_code: str
    contract_name: str
    reference_date: date
    open_interest: Decimal | None
    long_spec: Decimal | None
    short_spec: Decimal | None
    extra: dict[str, str]


class CftcProvider:
    name = "cftc"

    def fetch_latest(
        self,
        *,
        contracts: list[CotContractSpec] | None = None,
        client: httpx.Client | None = None,
        payload: bytes | None = None,
    ) -> list[CotRecord]:
        specs = contracts if contracts is not None else load_cot_contracts()
        if payload is not None:
            return parse_cot_rows(payload, specs)
        settings = get_settings()
        headers = {"User-Agent": f"{settings.http_user_agent}/{__version__}"}
        owns = client is None
        http_client = client or httpx.Client(timeout=settings.http_timeout_seconds, headers=headers)
        try:
            records: list[CotRecord] = []
            for url in (CFTC_DISAGGREGATED_URL, CFTC_TFF_URL):
                response = http_client.get(
                    url,
                    params={"$limit": "400", "$order": "report_date DESC"},
                )
                response.raise_for_status()
                records.extend(parse_cot_rows(response.content, specs))
            return _latest_per_contract(records)
        finally:
            if owns:
                http_client.close()


def parse_cot_rows(payload: bytes, specs: list[CotContractSpec]) -> list[CotRecord]:
    import json

    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, list):
        return []
    records: list[CotRecord] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(
            item.get("contract_market_name")
            or item.get("market_and_exchange_names")
            or item.get("Contract_Market_Name")
            or ""
        )
        matched = _match_contract(name, specs)
        if matched is None:
            continue
        raw_date = str(item.get("report_date") or item.get("Report_Date_as_YYYY-MM-DD") or "")
        if not raw_date:
            continue
        try:
            ref = date.fromisoformat(raw_date[:10])
        except ValueError:
            continue
        records.append(
            CotRecord(
                contract_code=matched.code,
                contract_name=name,
                reference_date=ref,
                open_interest=_cot_decimal(
                    item.get("open_interest_all") or item.get("Open_Interest_All")
                ),
                long_spec=_cot_decimal(
                    item.get("noncomm_positions_long_all")
                    or item.get("lev_money_positions_long_all")
                    or item.get("NonComm_Positions_Long_All")
                ),
                short_spec=_cot_decimal(
                    item.get("noncomm_positions_short_all")
                    or item.get("lev_money_positions_short_all")
                    or item.get("NonComm_Positions_Short_All")
                ),
                extra={"cftc_name": name},
            )
        )
    return records


def _match_contract(name: str, specs: list[CotContractSpec]) -> CotContractSpec | None:
    upper = name.upper()
    for spec in specs:
        if spec.name_contains.upper() in upper:
            # GOLD matches GOLD / GOLD - COMMODITY EXCHANGE INC. Avoid GOLDEN.
            if spec.code == "GC" and "GOLDEN" in upper:
                continue
            return spec
    return None


def _cot_decimal(raw: object) -> Decimal | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    if not text:
        return None
    try:
        return exact_decimal(text)
    except (InvalidFinancialValueError, InvalidOperation, ValueError):
        return None


def _latest_per_contract(records: list[CotRecord]) -> list[CotRecord]:
    latest: dict[str, CotRecord] = {}
    for record in records:
        previous = latest.get(record.contract_code)
        if previous is None or record.reference_date > previous.reference_date:
            latest[record.contract_code] = record
    return list(latest.values())
