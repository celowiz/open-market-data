"""Regression tests for the Oct/2026 scheduled-ingest failures."""

import json
import zipfile
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from marketdata.ingestion.config_tables import load_cot_contracts, load_scratch_issuers
from marketdata.providers.cftc import parse_cot_rows
from marketdata.providers.cvm_events import fato_relevante_url, parse_fato_relevante_csv

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

_IPE_HEADER = (
    "CNPJ_Companhia;Nome_Companhia;Codigo_CVM;Data_Referencia;Categoria;Tipo;Especie;"
    "Assunto;Data_Entrega;Tipo_Apresentacao;Protocolo_Entrega;Versao;Link_Download"
)
_IPE_ROWS = (
    "33.000.167/0001-01;PETROBRAS;9512;2026-08-21;Fato Relevante;;;"
    "Aumento de producao no pre-sal;2026-08-21;AP - Apresentação;009512IPE-001;1;"
    "https://www.rad.cvm.gov.br/doc-1",
    "33.000.167/0001-01;PETROBRAS;9512;2026-08-21;Assembleia;AGE;Ata;"
    "Ata da AGE;2026-08-22;AP - Apresentação;009512IPE-002;1;https://www.rad.cvm.gov.br/doc-2",
    "99.999.999/0001-91;OUTRA CIA;1;2026-08-21;Fato Relevante;;;Ignorado;2026-08-21;"
    "AP - Apresentação;000001IPE-003;1;https://www.rad.cvm.gov.br/doc-3",
)


def _ipe_zip() -> bytes:
    text = "\n".join((_IPE_HEADER, *_IPE_ROWS)) + "\n"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("ipe_cia_aberta_2026.csv", text.encode("latin-1"))
    return buffer.getvalue()


def test_cvm_events_url_points_to_ipe_dataset() -> None:
    url = fato_relevante_url(2026)
    assert url.endswith("/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_2026.zip")
    assert "FATO_RELEVANTE" not in url


def test_parse_ipe_zip_keeps_only_scratch_fatos_relevantes() -> None:
    rows = parse_fato_relevante_csv(_ipe_zip(), issuers=load_scratch_issuers())
    assert len(rows) == 1
    row = rows[0]
    assert row.ticker == "PETR4"
    assert row.headline == "Aumento de producao no pre-sal"
    assert row.external_id == "cvm-fato:009512IPE-001"
    assert row.url == "https://www.rad.cvm.gov.br/doc-1"
    assert row.occurred_at.date() == date(2026, 8, 21)


def test_parse_cot_rows_reads_current_socrata_field_names() -> None:
    payload = json.dumps(
        [
            {
                "market_and_exchange_names": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
                "contract_market_name": "E-MINI S&P 500",
                "report_date_as_yyyy_mm_dd": "2026-10-13T00:00:00.000",
                "open_interest_all": "1931607",
                "lev_money_positions_long": "121404",
                "lev_money_positions_short": "530130",
            },
            {
                "market_and_exchange_names": "CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE",
                "contract_market_name": "CRUDE OIL, LIGHT SWEET-WTI",
                "report_date_as_yyyy_mm_dd": "2026-10-13T00:00:00.000",
                "open_interest_all": "754570",
                "m_money_positions_long_all": "15990",
                "m_money_positions_short_all": "21056",
            },
        ]
    ).encode("utf-8")
    rows = {row.contract_code: row for row in parse_cot_rows(payload, load_cot_contracts())}
    assert set(rows) == {"SPX", "CL"}
    assert rows["SPX"].reference_date == date(2026, 10, 13)
    assert rows["SPX"].long_spec == Decimal("121404")
    assert rows["SPX"].short_spec == Decimal("530130")
    assert rows["CL"].long_spec == Decimal("15990")
    assert rows["CL"].short_spec == Decimal("21056")


def test_neon_write_workflows_apply_migrations_before_ingest() -> None:
    checked = 0
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if "group: neon-writes" not in text:
            continue
        checked += 1
        assert "DATABASE_URL: ${{ secrets.DATABASE_URL }}" in text, path.name
        migrate = text.find("run: uv run alembic upgrade head")
        assert migrate != -1, f"{path.name} must run alembic upgrade head"
        assert text.find("uv sync --frozen") < migrate, path.name
        first_marketdata = text.find("uv run marketdata ")
        if first_marketdata != -1:
            assert migrate < first_marketdata, path.name
    assert checked >= 10
