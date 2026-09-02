from sqlalchemy import Numeric

from marketdata.storage.models import Base, InstrumentQuoteRow, MarketSeriesObservationRow


def test_quotes_and_series_are_separate_tables() -> None:
    tables = set(Base.metadata.tables)
    assert "instrument_quotes" in tables
    assert "market_series_observations" in tables
    assert "market_series" in tables
    assert "instruments" in tables
    assert "instrument_identifiers" in tables
    assert "raw_artifacts" in tables
    assert "ingestion_runs" in tables
    assert "sources" in tables
    assert "curve_points" not in tables
    assert "events" in tables
    assert "lending_snapshots" in tables
    assert "cot_snapshots" in tables
    assert "thirteen_f_holdings" in tables
    assert InstrumentQuoteRow.__tablename__ != MarketSeriesObservationRow.__tablename__


def test_quote_value_uses_numeric() -> None:
    column = InstrumentQuoteRow.__table__.c.value
    assert isinstance(column.type, Numeric)
    assert column.type.precision == 38
    assert column.type.scale == 16
