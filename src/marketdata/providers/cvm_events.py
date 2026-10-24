from __future__ import annotations

import csv
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO, StringIO
from logging import getLogger

import httpx

from marketdata import __version__
from marketdata.config import get_settings
from marketdata.domain.identity import digits_only
from marketdata.ingestion.config_tables import load_scratch_issuers

# The standalone CVM FATO_RELEVANTE dataset URL returns HTTP 404.
# Fatos relevantes live in the IPE dataset (one zipped CSV per year), Categoria="Fato Relevante".
FATO_RELEVANTE_URL = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{year}.zip"
)
EVENT_TYPE_FATO = "fato_relevante"
IPE_CATEGORY_FATO = "fato relevante"
_HEADLINE_MAX = 512
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


def _extract_csv(payload: bytes) -> bytes:
    """Return the CSV bytes from a CVM payload (zipped IPE file or plain CSV)."""
    if not payload.startswith(b"PK"):
        return payload
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not names:
            return b""
        return archive.read(names[0])


def parse_fato_relevante_csv(payload: bytes, *, issuers: dict[str, str]) -> list[CvmFatoRecord]:
    """Parse CVM fatos relevantes from the IPE dataset (zip or CSV) or the legacy CSV layout."""
    text = _extract_csv(payload).decode("latin-1")
    reader = csv.DictReader(StringIO(text), delimiter=";")
    records: list[CvmFatoRecord] = []
    for row in reader:
        category = row.get("Categoria")
        if category is not None and category.strip().lower() != IPE_CATEGORY_FATO:
            continue
        cnpj = digits_only(
            row.get("CNPJ_Companhia") or row.get("CNPJ_CIA") or row.get("CNPJ") or ""
        )
        ticker = issuers.get(cnpj)
        if not ticker:
            continue
        headline = (
            row.get("Assunto") or row.get("ASSUNTO") or row.get("CATEGORIA_DOC") or ""
        ).strip()[:_HEADLINE_MAX]
        if not headline:
            continue
        occurred = _parse_cvm_datetime(
            row.get("Data_Entrega")
            or row.get("DT_ENTREGA")
            or row.get("Data_Referencia")
            or row.get("DT_REFER")
            or ""
        )
        link = (row.get("Link_Download") or row.get("LINK_DOC") or "").strip()
        protocol = (
            row.get("Protocolo_Entrega") or row.get("PROTOCOLO") or link or headline
        ).strip()
        version = (row.get("Versao") or "").strip()
        if version and version != "1" and row.get("Protocolo_Entrega"):
            protocol = f"{protocol}:v{version}"
        records.append(
            CvmFatoRecord(
                ticker=ticker,
                cnpj=cnpj,
                occurred_at=occurred,
                headline=headline,
                url=link[:1024] or None,
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
