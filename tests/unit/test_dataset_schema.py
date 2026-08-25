from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import polars as pl
import pytest

from marketdata.datasets.parquet import assert_value_not_float, write_parquet_bytes
from marketdata.datasets.schema import (
    FUND_NAV_SCHEMA,
    INSTRUMENTS_SCHEMA,
    QUOTES_SCHEMA,
    RATES_SCHEMA,
    SCHEMA_VERSION,
    SOURCES_SCHEMA,
    DatasetSchemaError,
    validate_frame,
)


def _quotes_row() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "instrument_id": str(uuid4()),
        "source": "cvm",
        "reference_date": date(2026, 8, 3),
        "value": Decimal("1.2345678901234567"),
        "currency": "BRL",
        "unit": "BRL",
        "price_type": "FUND_NAV",
        "is_official": True,
        "retrieved_at": datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
        "raw_artifact_id": str(uuid4()),
        "ingestion_run_id": str(uuid4()),
        "revision": 1,
        "quality_status": "ok",
        "ticker": None,
        "isin": None,
        "cnpj_fundo_classe": "00017024000153",
        "cvm_subclass_id": None,
        "title_type": None,
        "maturity_date": None,
    }


def test_quotes_schema_value_is_decimal_not_float() -> None:
    assert QUOTES_SCHEMA["value"] == pl.Decimal(38, 16)
    assert QUOTES_SCHEMA["price_type"] == pl.String
    assert FUND_NAV_SCHEMA["value"] == pl.Decimal(38, 16)
    assert RATES_SCHEMA["value"] == pl.Decimal(38, 16)
    assert "price_type" in QUOTES_SCHEMA
    assert "name" in SOURCES_SCHEMA
    assert "instrument_id" in INSTRUMENTS_SCHEMA


def test_validate_frame_accepts_explicit_quotes_schema() -> None:
    frame = pl.DataFrame([_quotes_row()], schema=QUOTES_SCHEMA)
    validate_frame(frame, QUOTES_SCHEMA)
    assert frame.schema["value"] == pl.Decimal(38, 16)


def test_validate_frame_rejects_float_value() -> None:
    frame = pl.DataFrame([_quotes_row()], schema=QUOTES_SCHEMA).with_columns(
        pl.col("value").cast(pl.Float64)
    )
    with pytest.raises(DatasetSchemaError, match="float"):
        validate_frame(frame, QUOTES_SCHEMA)


def test_parquet_round_trip_keeps_decimal_value() -> None:
    frame = pl.DataFrame([_quotes_row()], schema=QUOTES_SCHEMA)
    payload = write_parquet_bytes(frame)
    restored = pl.read_parquet(payload)
    assert_value_not_float(restored)
    dtype = restored.schema["value"]
    assert dtype != pl.Float32
    assert dtype != pl.Float64
    assert "price_type" in restored.columns
    assert restored["price_type"][0] == "FUND_NAV"
    assert Decimal(str(restored["value"][0])) == Decimal("1.2345678901234567")
