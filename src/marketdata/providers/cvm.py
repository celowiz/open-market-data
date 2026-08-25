from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import httpx

from marketdata import __version__
from marketdata.config import get_settings
from marketdata.domain.errors import InvalidFinancialValueError, exact_decimal
from marketdata.domain.identity import digits_only


class CvmParseError(ValueError):
    """Raised when an Informe Diário file cannot be interpreted."""


@dataclass(frozen=True)
class CvmDailyRecord:
    cnpj_fundo_classe: str
    subclass_id: str | None
    reference_date: date
    quota_value: Decimal
    net_assets: Decimal | None
    portfolio_value: Decimal | None
    inflows: Decimal | None
    outflows: Decimal | None
    shareholder_count: int | None
    schema_era: str
    raw: dict[str, str]


ERA_A = "A"
ERA_B = "B"
ERA_C = "C"


def detect_schema_era(header: list[str]) -> str:
    columns = {column.strip().upper() for column in header}
    if "CNPJ_FUNDO_CLASSE" in columns:
        return ERA_C
    if "TP_FUNDO" in columns and "CNPJ_FUNDO" in columns:
        return ERA_B
    if "CNPJ_FUNDO" in columns:
        return ERA_A
    raise CvmParseError(f"unrecognized CVM INF_DIARIO header: {header}")


def _csv_basename(name: str) -> str:
    return name.replace("\\", "/").rsplit("/", 1)[-1]


def _zip_csv_names(archive: zipfile.ZipFile) -> list[str]:
    names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if not names:
        raise CvmParseError("ZIP does not contain a CSV file")
    return names


def extract_csv_from_zip(payload: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = _zip_csv_names(archive)
        with archive.open(names[0]) as handle:
            return handle.read().decode("latin-1")


def iter_csv_members_from_zip(payload: bytes) -> Iterator[tuple[str, str]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in _zip_csv_names(archive):
            with archive.open(name) as handle:
                yield name, handle.read().decode("latin-1")


def extract_csv_members_from_zip(payload: bytes) -> list[tuple[str, str]]:
    """Return (inner_name, latin-1 text) for every *.csv in the ZIP (HIST has many)."""
    return list(iter_csv_members_from_zip(payload))


def iter_csv_members_for_month(payload: bytes, year: int, month: int) -> Iterator[tuple[str, str]]:
    """Yield CSV members whose filename contains YYYYMM. Does not decode the whole year."""
    token = f"{year:04d}{month:02d}"
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = _zip_csv_names(archive)
        matching = [name for name in names if token in _csv_basename(name)]
        for name in matching:
            with archive.open(name) as handle:
                yield name, handle.read().decode("latin-1")


def iter_informe_diario(csv_text: str) -> Iterator[CvmDailyRecord]:
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")
    if reader.fieldnames is None:
        raise CvmParseError("CSV is missing a header row")
    era = detect_schema_era(list(reader.fieldnames))

    def iterate() -> Iterator[CvmDailyRecord]:
        for row in reader:
            normalized = {key.strip(): (value or "").strip() for key, value in row.items() if key}
            parsed = _parse_row(normalized, era)
            if parsed is not None:
                yield parsed

    return iterate()


def parse_informe_diario(csv_text: str) -> list[CvmDailyRecord]:
    return list(iter_informe_diario(csv_text))


def _parse_row(row: dict[str, str], era: str) -> CvmDailyRecord | None:
    cnpj_raw = row.get("CNPJ_FUNDO_CLASSE") or row.get("CNPJ_FUNDO") or ""
    if not cnpj_raw:
        return None
    cnpj = digits_only(cnpj_raw)
    if len(cnpj) != 14:
        return None
    subclass = row.get("ID_SUBCLASSE") or None
    if subclass == "":
        subclass = None
    reference = _parse_date(row.get("DT_COMPTC", ""))
    if reference is None:
        return None
    quota = _parse_decimal(row.get("VL_QUOTA", ""))
    if quota is None:
        return None
    return CvmDailyRecord(
        cnpj_fundo_classe=cnpj,
        subclass_id=subclass,
        reference_date=reference,
        quota_value=quota,
        net_assets=_parse_decimal(row.get("VL_PATRIM_LIQ", "")),
        portfolio_value=_parse_decimal(row.get("VL_TOTAL", "")),
        inflows=_parse_decimal(row.get("CAPTC_DIA", "")),
        outflows=_parse_decimal(row.get("RESG_DIA", "")),
        shareholder_count=_parse_int(row.get("NR_COTST", "")),
        schema_era=era,
        raw=row,
    )


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_decimal(value: str) -> Decimal | None:
    if not value:
        return None
    cleaned = value.strip()
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return exact_decimal(cleaned)
    except (InvalidFinancialValueError, InvalidOperation, ValueError):
        return None


def _parse_int(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


CVM_MONTHLY_BASE = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS"
CVM_HIST_BASE = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/HIST"


def month_url(year: int, month: int) -> str:
    return f"{CVM_MONTHLY_BASE}/inf_diario_fi_{year:04d}{month:02d}.zip"


def hist_year_url(year: int) -> str:
    return f"{CVM_HIST_BASE}/inf_diario_fi_{year:04d}.zip"


def rolling_monthly_cutoff(as_of: date, months: int = 12) -> tuple[int, int]:
    """First year-month that must use DADOS/ monthly ZIPs rather than HIST."""
    if months < 1:
        raise ValueError("rolling window months must be >= 1")
    year = as_of.year
    month = as_of.month - (months - 1)
    while month <= 0:
        month += 12
        year -= 1
    return year, month


def uses_monthly_dados(year: int, month: int, as_of: date, *, months: int = 12) -> bool:
    return (year, month) >= rolling_monthly_cutoff(as_of, months=months)


def months_in_range(start: date, end: date) -> list[tuple[int, int]]:
    if end < start:
        raise ValueError("end must be on or after start")
    months: list[tuple[int, int]] = []
    cursor = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    while cursor <= last:
        months.append((cursor.year, cursor.month))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return months


def months_covering(end: date, lookback_days: int) -> list[tuple[int, int]]:
    return months_in_range(end - timedelta(days=lookback_days), end)


def _cvm_http_get(url: str, *, client: httpx.Client | None = None) -> httpx.Response:
    settings = get_settings()
    headers = {"User-Agent": f"{settings.http_user_agent}/{__version__}"}
    owns_client = client is None
    http_client = client or httpx.Client(
        timeout=settings.http_timeout_seconds,
        follow_redirects=True,
        headers=headers,
    )
    try:
        response = http_client.get(url)
        response.raise_for_status()
        return response
    finally:
        if owns_client:
            http_client.close()


class CvmProvider:
    name = "cvm"

    def month_url(self, year: int, month: int) -> str:
        return month_url(year, month)

    def hist_year_url(self, year: int) -> str:
        return hist_year_url(year)

    def fetch_month(
        self, year: int, month: int, *, client: httpx.Client | None = None
    ) -> httpx.Response:
        return _cvm_http_get(self.month_url(year, month), client=client)

    def fetch_hist_year(self, year: int, *, client: httpx.Client | None = None) -> httpx.Response:
        return _cvm_http_get(self.hist_year_url(year), client=client)
