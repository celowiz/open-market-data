import io
import zipfile
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from marketdata.ingestion.cvm import backfill_cvm, ingest_cvm
from marketdata.providers.cvm import CvmProvider, parse_cvm_class_allowlist
from marketdata.storage.models import Base, InstrumentQuoteRow, InstrumentRow
from marketdata.storage.object_store import LocalFileObjectStorage

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cvm"
REGISTRO_CLASSE = (FIXTURES / "registro_classe.csv").read_text(encoding="latin-1")
ERA_C_HEADER = (
    "TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;ID_SUBCLASSE;DT_COMPTC;"
    "VL_TOTAL;VL_QUOTA;VL_PATRIM_LIQ;CAPTC_DIA;RESG_DIA;NR_COTST"
)
SCRATCH_CLASSES = "Multimercado,Ações"

FUNDS = {
    "multimercado": ("11.111.111/0001-11", "11111111000111"),
    "acoes": ("22.222.222/0001-22", "22222222000122"),
    "renda_fixa": ("33.333.333/0001-33", "33333333000133"),
    "fii": ("44.444.444/0001-44", "44444444000144"),
    "fidc": ("55.555.555/0001-55", "55555555000155"),
    "unclassified": ("66.666.666/0001-66", "66666666000166"),
}


class _FakeResponse:
    def __init__(self, content: bytes, url: str) -> None:
        self.content = content
        self.status_code = 200
        self.headers = {"content-type": "application/zip"}
        self.request = type("Req", (), {"url": url})()


class _FakeCvm(CvmProvider):
    def __init__(self, informe: bytes, cadastro: bytes) -> None:
        self._informe = informe
        self._cadastro = cadastro
        self.cadastro_fetches = 0

    def fetch_month(self, year: int, month: int, *, client=None) -> _FakeResponse:
        return _FakeResponse(self._informe, self.month_url(year, month))

    def fetch_cadastro(self, *, client=None) -> _FakeResponse:
        self.cadastro_fetches += 1
        return _FakeResponse(self._cadastro, self.cadastro_url())


def _zip_members(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text.encode("latin-1"))
    return buffer.getvalue()


def _informe_csv(rows: list[tuple[str, str]]) -> str:
    lines = [ERA_C_HEADER]
    for punctuated_cnpj, quota in rows:
        lines.append(
            f"CLASSES - FIF;{punctuated_cnpj};;2026-01-15;100.00;{quota};100.00;0.00;0.00;1"
        )
    return "\n".join(lines) + "\n"


def _all_funds_informe() -> bytes:
    rows = [(punctuated, "1.25") for punctuated, _digits in FUNDS.values()]
    return _zip_members({"inf_diario_fi_202601.csv": _informe_csv(rows)})


def _cadastro_zip() -> bytes:
    return _zip_members({"registro_classe.csv": REGISTRO_CLASSE})


@pytest.fixture
def sqlite_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


def _quote_cnpjs(session) -> set[str]:
    return {row.source_instrument_id for row in session.scalars(select(InstrumentQuoteRow))}


def test_allowlist_persists_multimercado_and_acoes_only(sqlite_session, tmp_path) -> None:
    provider = _FakeCvm(_all_funds_informe(), _cadastro_zip())
    result = ingest_cvm(
        sqlite_session,
        reference_date=date(2026, 1, 15),
        lookback_days=0,
        storage=LocalFileObjectStorage(tmp_path),
        provider=provider,
        class_allowlist=parse_cvm_class_allowlist(SCRATCH_CLASSES),
    )
    kept = _quote_cnpjs(sqlite_session)
    assert kept == {FUNDS["multimercado"][1], FUNDS["acoes"][1]}
    assert FUNDS["fii"][1] not in kept
    assert FUNDS["fidc"][1] not in kept
    assert FUNDS["renda_fixa"][1] not in kept
    assert FUNDS["unclassified"][1] not in kept
    assert int(result["inserted"]) == 2
    assert provider.cadastro_fetches == 1
    storage = LocalFileObjectStorage(tmp_path)
    assert storage.exists("raw/cvm/cadastro/registro_fundo_classe.zip")


def test_persisted_instrument_stores_cadastro_classe(sqlite_session, tmp_path) -> None:
    provider = _FakeCvm(_all_funds_informe(), _cadastro_zip())
    ingest_cvm(
        sqlite_session,
        reference_date=date(2026, 1, 15),
        lookback_days=0,
        storage=LocalFileObjectStorage(tmp_path),
        provider=provider,
        class_allowlist=parse_cvm_class_allowlist(SCRATCH_CLASSES),
    )
    instruments = list(sqlite_session.scalars(select(InstrumentRow)))
    by_name = {row.name: row for row in instruments}
    multi = by_name["Fundo Multimercado Fixture"]
    acoes = by_name["Fundo Acoes Fixture"]
    assert multi.extra["classe"] == "Multimercado"
    assert acoes.extra["classe"] == "Ações"
    assert multi.instrument_type == "fund_class"
    quotes = list(sqlite_session.scalars(select(InstrumentQuoteRow)))
    assert all(row.price_type == "FUND_NAV" for row in quotes)
    assert all("classe" not in (row.extra or {}) for row in quotes)


def test_unset_cvm_classes_persists_all_funds(sqlite_session, tmp_path) -> None:
    provider = _FakeCvm(_all_funds_informe(), _cadastro_zip())
    result = ingest_cvm(
        sqlite_session,
        reference_date=date(2026, 1, 15),
        lookback_days=0,
        storage=LocalFileObjectStorage(tmp_path),
        provider=provider,
        class_allowlist=None,
    )
    kept = _quote_cnpjs(sqlite_session)
    assert kept == {digits for _punctuated, digits in FUNDS.values()}
    assert int(result["inserted"]) == len(FUNDS)


def test_backfill_honors_the_same_class_allowlist(sqlite_session, tmp_path) -> None:
    provider = _FakeCvm(_all_funds_informe(), _cadastro_zip())
    result = backfill_cvm(
        sqlite_session,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        storage=LocalFileObjectStorage(tmp_path),
        provider=provider,
        as_of=date(2026, 1, 20),
        class_allowlist=parse_cvm_class_allowlist(SCRATCH_CLASSES),
    )
    kept = _quote_cnpjs(sqlite_session)
    assert kept == {FUNDS["multimercado"][1], FUNDS["acoes"][1]}
    assert int(result["inserted"]) == 2
    assert provider.cadastro_fetches == 1
