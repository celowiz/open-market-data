import io
import zipfile
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from marketdata.ingestion.checkpoint import load_checkpoint
from marketdata.ingestion.cvm import backfill_cvm
from marketdata.providers.cvm import (
    CvmProvider,
    extract_csv_members_from_zip,
    hist_year_url,
    rolling_monthly_cutoff,
)
from marketdata.storage.models import Base, InstrumentQuoteRow
from marketdata.storage.object_store import LocalFileObjectStorage

ERA_C_HEADER = (
    "TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;ID_SUBCLASSE;DT_COMPTC;"
    "VL_TOTAL;VL_QUOTA;VL_PATRIM_LIQ;CAPTC_DIA;RESG_DIA;NR_COTST"
)
CNPJ = "00.017.024/0001-53"


class _FakeResponse:
    def __init__(self, content: bytes, url: str) -> None:
        self.content = content
        self.status_code = 200
        self.headers = {"content-type": "application/zip"}
        self.request = type("Req", (), {"url": url})()


class _FakeCvm(CvmProvider):
    def __init__(
        self,
        *,
        monthly: dict[tuple[int, int], bytes] | None = None,
        hist: dict[int, bytes] | None = None,
    ) -> None:
        self._monthly = monthly or {}
        self._hist = hist or {}
        self.month_fetches: list[tuple[int, int]] = []
        self.hist_fetches: list[int] = []

    def fetch_month(self, year: int, month: int, *, client=None) -> _FakeResponse:
        self.month_fetches.append((year, month))
        payload = self._monthly.get((year, month))
        if payload is None:
            raise AssertionError(f"unexpected monthly fetch for {year:04d}-{month:02d}")
        return _FakeResponse(payload, self.month_url(year, month))

    def fetch_hist_year(self, year: int, *, client=None) -> _FakeResponse:
        self.hist_fetches.append(year)
        payload = self._hist.get(year)
        if payload is None:
            raise AssertionError(f"unexpected HIST fetch for {year}")
        return _FakeResponse(payload, self.hist_year_url(year))

    def fetch_cadastro(self, *, client=None) -> _FakeResponse:
        return _FakeResponse(_empty_cadastro_zip(), self.cadastro_url())


def _informe_csv(reference: date, quota: str) -> str:
    row = f"CLASSES - FIF;{CNPJ};;{reference.isoformat()};100.00;{quota};100.00;0.00;0.00;1"
    return f"{ERA_C_HEADER}\n{row}\n"


def _zip_members(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text.encode("latin-1"))
    return buffer.getvalue()


def _empty_cadastro_zip() -> bytes:
    header = "CNPJ_Classe;Classificacao;Tipo_Classe;Denominacao_Social;Situacao\n"
    return _zip_members({"registro_classe.csv": header})


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


def test_hist_year_url_2018_uses_dados_hist() -> None:
    url = hist_year_url(2018)
    assert "/DADOS/HIST/" in url
    assert url.endswith("inf_diario_fi_2018.zip")
    assert "inf_diario_fi_201801.zip" not in url
    assert (
        url == "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/HIST/inf_diario_fi_2018.zip"
    )


def test_rolling_monthly_cutoff_is_twelve_months_inclusive() -> None:
    assert rolling_monthly_cutoff(date(2026, 8, 24)) == (2025, 9)
    assert rolling_monthly_cutoff(date(2026, 1, 15), months=12) == (2025, 2)


def test_extract_csv_members_from_zip_returns_every_csv() -> None:
    payload = _zip_members(
        {
            "inf_diario_fi_201801.csv": _informe_csv(date(2018, 1, 15), "1.25"),
            "inf_diario_fi_201802.csv": _informe_csv(date(2018, 2, 15), "2.50"),
        }
    )
    members = extract_csv_members_from_zip(payload)
    names = [name for name, _text in members]
    assert names == ["inf_diario_fi_201801.csv", "inf_diario_fi_201802.csv"]
    assert "1.25" in members[0][1]
    assert "2.50" in members[1][1]


def test_hist_backfill_persists_only_months_in_range(sqlite_session, tmp_path) -> None:
    hist_zip = _zip_members(
        {
            "inf_diario_fi_201801.csv": _informe_csv(date(2018, 1, 15), "1.25"),
            "inf_diario_fi_201802.csv": _informe_csv(date(2018, 2, 15), "2.50"),
        }
    )
    provider = _FakeCvm(hist={2018: hist_zip})
    storage = LocalFileObjectStorage(tmp_path)

    result = backfill_cvm(
        sqlite_session,
        start=date(2018, 1, 1),
        end=date(2018, 1, 31),
        storage=storage,
        provider=provider,
        as_of=date(2026, 8, 24),
    )

    assert provider.hist_fetches == [2018]
    assert provider.month_fetches == []
    assert storage.exists("raw/cvm/hist/inf_diario_fi_2018.zip")
    assert int(result["inserted"]) == 1

    rows = sqlite_session.scalars(select(InstrumentQuoteRow)).all()
    assert len(rows) == 1
    assert rows[0].reference_date == date(2018, 1, 15)
    assert rows[0].value == Decimal("1.25")
    assert not isinstance(rows[0].value, float)

    checkpoint = load_checkpoint(storage, "cvm")
    assert checkpoint is not None
    assert checkpoint.last_completed == "2018-01"
    assert checkpoint.status == "succeeded"


def test_backfill_uses_monthly_url_inside_rolling_window(sqlite_session, tmp_path) -> None:
    monthly_zip = _zip_members({"inf_diario_fi_202608.csv": _informe_csv(date(2026, 8, 3), "1.5")})
    provider = _FakeCvm(monthly={(2026, 8): monthly_zip})
    storage = LocalFileObjectStorage(tmp_path)

    result = backfill_cvm(
        sqlite_session,
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        storage=storage,
        provider=provider,
        as_of=date(2026, 8, 24),
    )

    assert provider.month_fetches == [(2026, 8)]
    assert provider.hist_fetches == []
    monthly_url = provider.month_url(2026, 8)
    assert monthly_url.endswith("/DADOS/inf_diario_fi_202608.zip")
    assert "/HIST/" not in monthly_url
    assert int(result["inserted"]) == 1

    rows = sqlite_session.scalars(select(InstrumentQuoteRow)).all()
    assert len(rows) == 1
    assert rows[0].reference_date == date(2026, 8, 3)
    assert isinstance(rows[0].value, Decimal)
    assert not isinstance(rows[0].value, float)
    assert rows[0].value == Decimal("1.5")


def test_hist_year_fetched_once_for_two_months(sqlite_session, tmp_path) -> None:
    hist_zip = _zip_members(
        {
            "inf_diario_fi_201801.csv": _informe_csv(date(2018, 1, 15), "1.25"),
            "inf_diario_fi_201802.csv": _informe_csv(date(2018, 2, 15), "2.50"),
        }
    )
    provider = _FakeCvm(hist={2018: hist_zip})
    storage = LocalFileObjectStorage(tmp_path)

    result = backfill_cvm(
        sqlite_session,
        start=date(2018, 1, 1),
        end=date(2018, 2, 28),
        storage=storage,
        provider=provider,
        as_of=date(2026, 8, 24),
    )

    assert provider.hist_fetches == [2018]
    assert provider.month_fetches == []
    assert int(result["inserted"]) == 2
    dates = {row.reference_date for row in sqlite_session.scalars(select(InstrumentQuoteRow))}
    assert dates == {date(2018, 1, 15), date(2018, 2, 15)}


def test_backfill_resumes_from_monthly_checkpoint(sqlite_session, tmp_path) -> None:
    hist_zip = _zip_members(
        {
            "inf_diario_fi_201801.csv": _informe_csv(date(2018, 1, 15), "1.25"),
            "inf_diario_fi_201802.csv": _informe_csv(date(2018, 2, 15), "2.50"),
        }
    )
    provider = _FakeCvm(hist={2018: hist_zip})
    storage = LocalFileObjectStorage(tmp_path)
    kwargs = dict(
        start=date(2018, 1, 1),
        end=date(2018, 2, 28),
        storage=storage,
        provider=provider,
        as_of=date(2026, 8, 24),
        resume=True,
    )

    first = backfill_cvm(sqlite_session, max_months=1, **kwargs)
    assert int(first["inserted"]) == 1
    assert int(first["months"]) == 1
    checkpoint = load_checkpoint(storage, "cvm")
    assert checkpoint is not None
    assert checkpoint.last_completed == "2018-01"
    assert checkpoint.status == "running"

    second = backfill_cvm(sqlite_session, **kwargs)
    assert int(second["inserted"]) == 1
    assert provider.hist_fetches == [2018]
    assert provider.month_fetches == []
    dates = {row.reference_date for row in sqlite_session.scalars(select(InstrumentQuoteRow))}
    assert dates == {date(2018, 1, 15), date(2018, 2, 15)}
    checkpoint = load_checkpoint(storage, "cvm")
    assert checkpoint is not None
    assert checkpoint.last_completed == "2018-02"
    assert checkpoint.status == "succeeded"


def test_backfill_cvm_later_month_quote_does_not_skip_earlier_months(
    sqlite_session, tmp_path
) -> None:
    """A later month already in Neon must not skip earlier HIST months."""
    hist_zip = _zip_members(
        {
            "inf_diario_fi_201801.csv": _informe_csv(date(2018, 1, 15), "1.25"),
            "inf_diario_fi_201802.csv": _informe_csv(date(2018, 2, 15), "2.50"),
        }
    )
    provider = _FakeCvm(hist={2018: hist_zip})
    storage = LocalFileObjectStorage(tmp_path)
    first = backfill_cvm(
        sqlite_session,
        start=date(2018, 2, 1),
        end=date(2018, 2, 28),
        storage=storage,
        provider=provider,
        as_of=date(2026, 8, 24),
        resume=True,
    )
    assert int(first["inserted"]) == 1
    (tmp_path / "state" / "backfill" / "cvm.json").unlink()

    second = backfill_cvm(
        sqlite_session,
        start=date(2018, 1, 1),
        end=date(2018, 2, 28),
        storage=LocalFileObjectStorage(tmp_path / "second"),
        provider=provider,
        as_of=date(2026, 8, 24),
        resume=True,
    )
    assert int(second["months"]) == 2
    dates = {row.reference_date for row in sqlite_session.scalars(select(InstrumentQuoteRow))}
    assert dates == {date(2018, 1, 15), date(2018, 2, 15)}
