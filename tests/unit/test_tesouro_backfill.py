from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from marketdata.config import get_settings
from marketdata.domain.enums import PriceType
from marketdata.ingestion.checkpoint import load_checkpoint
from marketdata.ingestion.tesouro import backfill_tesouro
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import InstrumentQuoteRow
from marketdata.storage.object_store import LocalFileObjectStorage
from marketdata.storage.repositories import resolve_instrument_id

# Three Data Base days; start/end keeps the middle two (11/01 and 12/01).
_HEADER = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;"
    "PU Compra Manha;PU Venda Manha;PU Base Manha"
)
THREE_DAY_CSV = "\n".join(
    [
        _HEADER,
        "Tesouro Prefixado;01/01/2035;10/01/2025;14,00;14,10;111,11;111,11;111,11",
        "Tesouro Prefixado;01/01/2035;11/01/2025;14,20;14,30;222,22;222,22;222,22",
        "Tesouro Prefixado;01/01/2035;12/01/2025;14,40;14,50;333,33;333,33;333,33",
        "",
    ]
)

RANGE_START = date(2025, 1, 11)
RANGE_END = date(2025, 1, 12)
INSTRUMENT_KEY = "LTN:2035-01-01"
EXCLUDED_DATE = date(2025, 1, 10)
RAW_KEY = "raw/tesouro/backfill/precotaxatesourodireto-2025-01-11_2025-01-12.csv"


class _FakeResponse:
    def __init__(self, content: bytes, url: str) -> None:
        self.content = content
        self.status_code = 200
        self.headers = {"content-type": "text/csv"}
        self.request = type("Req", (), {"url": url})()


class _FakeTesouro:
    name = "tesouro"

    def __init__(self, csv_text: str) -> None:
        self._csv_text = csv_text
        self.fetch_calls = 0

    def csv_url(self) -> str:
        return "https://example.test/precotaxatesourodireto.csv"

    def fetch_csv(self, *, client=None):
        del client
        self.fetch_calls += 1
        if self.fetch_calls > 1:
            raise AssertionError("Tesouro CSV must be downloaded once per backfill")
        return _FakeResponse(self._csv_text.encode("utf-8"), self.csv_url())


@pytest.fixture
def db_session():
    settings = get_settings()
    if not settings.database_url:
        pytest.skip("DATABASE_URL is not configured")
    factory = create_session_factory(create_db_engine(settings))
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _quotes_for(session, instrument_id) -> list[InstrumentQuoteRow]:
    return list(
        session.scalars(
            select(InstrumentQuoteRow).where(InstrumentQuoteRow.instrument_id == instrument_id)
        )
    )


def _pu_base_by_date(session, instrument_id) -> dict[date, Decimal]:
    rows = session.scalars(
        select(InstrumentQuoteRow).where(
            InstrumentQuoteRow.instrument_id == instrument_id,
            InstrumentQuoteRow.price_type == PriceType.PU_BASE.value,
        )
    )
    return {row.reference_date: row.value for row in rows}


@pytest.mark.db
def test_backfill_keeps_only_dates_inside_start_end(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    result = backfill_tesouro(
        db_session,
        start=RANGE_START,
        end=RANGE_END,
        storage=storage,
        csv_text=THREE_DAY_CSV,
    )
    db_session.commit()

    assert result["status"] == "succeeded"
    assert int(result["inserted"]) + int(result["updated"]) + int(result["skipped"]) == 10

    instrument_id = resolve_instrument_id(db_session, INSTRUMENT_KEY)
    assert instrument_id is not None
    quotes = _quotes_for(db_session, instrument_id)
    dates = {row.reference_date for row in quotes}
    assert EXCLUDED_DATE not in dates
    assert dates == {RANGE_START, RANGE_END}
    assert len(quotes) == 10

    assert storage.exists(RAW_KEY)
    checkpoint = load_checkpoint(storage, "tesouro")
    assert checkpoint is not None
    assert checkpoint.provider == "tesouro"
    assert checkpoint.start == RANGE_START.isoformat()
    assert checkpoint.end == RANGE_END.isoformat()
    assert checkpoint.last_completed == RANGE_END.isoformat()
    assert checkpoint.status == "succeeded"


@pytest.mark.db
def test_backfill_fetches_csv_once_for_multi_day_range(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    provider = _FakeTesouro(THREE_DAY_CSV)
    backfill_tesouro(
        db_session,
        start=RANGE_START,
        end=RANGE_END,
        storage=storage,
        provider=provider,
    )
    assert provider.fetch_calls == 1


@pytest.mark.db
def test_backfill_persists_decimal_values_not_float(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    backfill_tesouro(
        db_session,
        start=RANGE_START,
        end=RANGE_END,
        storage=storage,
        csv_text=THREE_DAY_CSV,
    )
    db_session.commit()

    instrument_id = resolve_instrument_id(db_session, INSTRUMENT_KEY)
    assert instrument_id is not None
    pu_base = _pu_base_by_date(db_session, instrument_id)
    assert pu_base[RANGE_START] == Decimal("222.22")
    assert pu_base[RANGE_END] == Decimal("333.33")
    assert EXCLUDED_DATE not in pu_base
    for value in pu_base.values():
        assert type(value) is Decimal
        assert not isinstance(value, float)


@pytest.mark.db
def test_backfill_is_idempotent_on_same_csv(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    first = backfill_tesouro(
        db_session,
        start=RANGE_START,
        end=RANGE_END,
        storage=storage,
        csv_text=THREE_DAY_CSV,
        resume=False,
    )
    db_session.commit()
    second = backfill_tesouro(
        db_session,
        start=RANGE_START,
        end=RANGE_END,
        storage=storage,
        csv_text=THREE_DAY_CSV,
        resume=False,
    )
    assert int(first["inserted"]) + int(first["updated"]) + int(first["skipped"]) == 10
    assert second["inserted"] == 0
    assert int(second["skipped"]) >= 1
