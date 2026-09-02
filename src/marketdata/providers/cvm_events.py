from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from logging import getLogger

import httpx

from marketdata import __version__
from marketdata.config import get_settings
from marketdata.domain.identity import digits_only
from marketdata.ingestion.config_tables import load_scratch_issuers

FATO_RELEVANTE_URL = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FATO_RELEVANTE/DADOS/"
    "fato_relevante_cia_aberta_{year}.csv"
)
EVENT_TYPE_FATO = "fato_relevante"
logger = getLogger(__name__)


@dataclass(frozen=True)
class CvmFatoRecord:
    ticker: str
    cnpj: str
    occurred_at: datetime
    headline: str
    url: str | None
    external_id: str


class CvmEventsProvider:
    name = "cvm"

    def fetch_year(
        self,
        year: int,
        *,
        issuers: dict[str, str] | None = None,
        client: httpx.Client | None = None,
        payload: bytes | None = None,
    ) -> list[CvmFatoRecord]:
        mapping = issuers if issuers is not None else load_scratch_issuers()
        if payload is None:
            settings = get_settings()
            headers = {"User-Agent": f"{settings.http_user_agent}/{__version__}"}
            owns = client is None
            http_client = client or httpx.Client(
                timeout=settings.http_timeout_seconds, headers=headers, follow_redirects=True
            )
            url = FATO_RELEVANTE_URL.format(year=year)
            try:
                response = http_client.get(url)
                response.raise_for_status()
                payload = response.content
            finally:
                if owns:
                    http_client.close()
        return parse_fato_relevante_csv(payload, issuers=mapping)


def parse_fato_relevante_csv(payload: bytes, *, issuers: dict[str, str]) -> list[CvmFatoRecord]:
    text = payload.decode("latin-1")
    reader = csv.DictReader(StringIO(text), delimiter=";")
    records: list[CvmFatoRecord] = []
    for row in reader:
        cnpj = digits_only(row.get("CNPJ_CIA") or row.get("CNPJ") or "")
        ticker = issuers.get(cnpj)
        if not ticker:
            continue
        headline = (row.get("ASSUNTO") or row.get("CATEGORIA_DOC") or "").strip()
        if not headline:
            continue
        occurred = _parse_cvm_datetime(row.get("DT_ENTREGA") or row.get("DT_REFER") or "")
        protocol = (row.get("PROTOCOLO") or row.get("LINK_DOC") or headline).strip()
        records.append(
            CvmFatoRecord(
                ticker=ticker,
                cnpj=cnpj,
                occurred_at=occurred,
                headline=headline,
                url=(row.get("LINK_DOC") or "").strip() or None,
                external_id=f"cvm-fato:{protocol}",
            )
        )
    return records


def _parse_cvm_datetime(raw: str) -> datetime:
    text = raw.strip()
    if not text:
        return datetime.now(UTC)
    try:
        if "T" in text:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(text[:10])
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return datetime.now(UTC)


def fato_relevante_url(year: int) -> str:
    return FATO_RELEVANTE_URL.format(year=year)
