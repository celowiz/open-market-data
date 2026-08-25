from datetime import date
from decimal import Decimal
from json import loads

import pytest
from sqlalchemy import select

from marketdata.config import get_settings
from marketdata.domain.enums import PriceType, RedistributionPolicy
from marketdata.ingestion.checkpoint import load_checkpoint
from marketdata.ingestion.yahoo import DEFAULT_YAHOO_SYMBOLS, backfill_yahoo
from marketdata.providers.yahoo import YahooQuoteRecord, parse_yahoo_history
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import InstrumentQuoteRow, SourceRow
from marketdata.storage.object_store import LocalFileObjectStorage
from marketdata.storage.repositories import resolve_instrument_id

START = date(2020, 1, 1)
END = date(2020, 1, 31)
SESSION_DAY = date(2020, 1, 15)
CLOSE = Decimal("185.64")
ADJ_CLOSE = Decimal("180.00")


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


class FakeYahooProvider:
    name = "yahoo"

    def __init__(self) -> None:
        self.calls: list[tuple[str, date, date]] = []

    def fetch_history(self, symbol: str, *, start: date, end: date) -> list[YahooQuoteRecord]:
        self.calls.append((symbol, start, end))
        return parse_yahoo_history(
            symbol,
            [
                {
                    "date": SESSION_DAY,
                    "Close": str(CLOSE),
                    "Adj Close": str(ADJ_CLOSE),
                    "Open": "184.00",
                }
            ],
            currency="USD",
        )


class ExplodingYahooProvider:
    name = "yahoo"

    def fetch_history(self, symbol: str, *, start: date, end: date) -> list[YahooQuoteRecord]:
        raise AssertionError(
            f"provider must not be called when history_rows is injected ({symbol})"
        )


def _history_row(
    symbol: str,
    reference_date: date = SESSION_DAY,
    value: Decimal = CLOSE,
) -> YahooQuoteRecord:
    return YahooQuoteRecord(
        symbol=symbol,
        reference_date=reference_date,
        value=value,
        currency="USD",
        source_field="Close",
    )


def _close_quotes(
    db_session,
    identifier: str,
    *,
    reference_date: date = SESSION_DAY,
) -> list[InstrumentQuoteRow]:
    instrument_id = resolve_instrument_id(db_session, identifier)
    assert instrument_id is not None
    return list(
        db_session.scalars(
            select(InstrumentQuoteRow)
            .where(
                InstrumentQuoteRow.instrument_id == instrument_id,
                InstrumentQuoteRow.reference_date == reference_date,
                InstrumentQuoteRow.price_type == PriceType.CLOSE.value,
            )
            .order_by(InstrumentQuoteRow.revision.desc())
        )
    )


@pytest.mark.db
def test_backfill_yahoo_calls_fetch_history_once_per_symbol(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    provider = FakeYahooProvider()

    result = backfill_yahoo(
        db_session,
        start=START,
        end=END,
        symbols=["AAPL", "MSFT"],
        storage=storage,
        provider=provider,
    )
    db_session.commit()

    assert [symbol for symbol, _, _ in provider.calls] == ["AAPL", "MSFT"]
    assert len(provider.calls) == 2
    for _, called_start, called_end in provider.calls:
        assert called_start == START
        assert called_end >= END
        assert (called_end - START).days < 40
    assert int(result["inserted"]) + int(result["updated"]) + int(result["skipped"]) >= 2


@pytest.mark.db
def test_backfill_yahoo_uses_close_not_adj_close(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    backfill_yahoo(
        db_session,
        start=START,
        end=END,
        symbols=["AAPL"],
        storage=storage,
        provider=FakeYahooProvider(),
    )
    db_session.commit()

    quotes = _close_quotes(db_session, "AAPL")
    assert quotes
    assert quotes[0].price_type == PriceType.CLOSE.value
    assert Decimal(quotes[0].value) == CLOSE
    assert Decimal(quotes[0].value) != ADJ_CLOSE
    assert quotes[0].extra.get("source_field") == "Close"
    assert quotes[0].is_official is False


@pytest.mark.db
def test_backfill_yahoo_persists_decimal_not_float(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    backfill_yahoo(
        db_session,
        start=START,
        end=END,
        symbols=["AAPL"],
        storage=storage,
        history_rows=[_history_row("AAPL")],
        provider=ExplodingYahooProvider(),
    )
    db_session.commit()

    quotes = _close_quotes(db_session, "AAPL")
    assert quotes
    assert isinstance(quotes[0].value, Decimal)
    assert not isinstance(quotes[0].value, float)

    raw_path = (
        tmp_path
        / "raw"
        / "yahoo"
        / "backfill"
        / "AAPL"
        / f"{START.isoformat()}_{END.isoformat()}.json"
    )
    payload = loads(raw_path.read_text(encoding="utf-8"))
    assert payload
    assert isinstance(payload[0]["close"], str)
    assert payload[0]["close"] == "185.64"
    assert "." in payload[0]["close"] or payload[0]["close"].isdigit()


@pytest.mark.db
def test_backfill_yahoo_history_rows_skips_provider(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    result = backfill_yahoo(
        db_session,
        start=START,
        end=END,
        symbols=["AAPL"],
        storage=storage,
        history_rows=[
            _history_row("AAPL", date(2019, 12, 31), Decimal("1.00")),
            _history_row("AAPL", SESSION_DAY, CLOSE),
            _history_row("AAPL", date(2020, 2, 1), Decimal("9.00")),
            _history_row("NOPE", SESSION_DAY, Decimal("150.00")),
        ],
        provider=ExplodingYahooProvider(),
    )
    db_session.commit()

    quotes = _close_quotes(db_session, "AAPL")
    assert quotes
    assert quotes[0].reference_date == SESSION_DAY
    assert Decimal(quotes[0].value) == CLOSE
    assert int(result["inserted"]) + int(result["updated"]) + int(result["skipped"]) >= 1
    assert resolve_instrument_id(db_session, "NOPE") is None


@pytest.mark.db
def test_backfill_yahoo_enables_public_api_and_checkpoints(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    result = backfill_yahoo(
        db_session,
        start=START,
        end=END,
        symbols=None,
        storage=storage,
        provider=FakeYahooProvider(),
    )
    db_session.commit()

    source = db_session.scalar(select(SourceRow).where(SourceRow.name == "yahoo"))
    assert source is not None
    assert source.public_api_enabled is True
    assert source.public_dataset_enabled is False
    assert source.official is False
    assert source.redistribution_policy == RedistributionPolicy.UNKNOWN.value
    assert source.ingestion_enabled is True

    checkpoint = load_checkpoint(storage, "yahoo")
    assert checkpoint is not None
    assert checkpoint.provider == "yahoo"
    assert checkpoint.start == START.isoformat()
    assert checkpoint.end == END.isoformat()
    assert checkpoint.status == "succeeded"
    assert checkpoint.last_completed == DEFAULT_YAHOO_SYMBOLS[-1]

    assert result["status"]
    raw_path = (
        tmp_path
        / "raw"
        / "yahoo"
        / "backfill"
        / "AAPL"
        / f"{START.isoformat()}_{END.isoformat()}.json"
    )
    assert raw_path.exists()


@pytest.mark.db
def test_backfill_yahoo_second_run_is_idempotent(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    rows = [_history_row("AAPL")]
    first = backfill_yahoo(
        db_session,
        start=START,
        end=END,
        symbols=["AAPL"],
        storage=storage,
        history_rows=rows,
        provider=ExplodingYahooProvider(),
    )
    db_session.commit()
    second = backfill_yahoo(
        db_session,
        start=START,
        end=END,
        symbols=["AAPL"],
        storage=storage,
        history_rows=rows,
        provider=ExplodingYahooProvider(),
    )
    db_session.commit()

    assert int(first["inserted"]) + int(first["updated"]) + int(first["skipped"]) >= 1
    assert second["inserted"] == 0
    assert int(second["skipped"]) >= 1
    quotes = _close_quotes(db_session, "AAPL")
    assert Decimal(quotes[0].value) == CLOSE
