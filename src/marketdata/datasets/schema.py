import polars as pl

SCHEMA_VERSION = "1"
VALUE_DTYPE = pl.Decimal(38, 16)
UTC_DATETIME = pl.Datetime(time_unit="us", time_zone="UTC")
type PolarsDType = pl.DataType | type[pl.DataType]

QUOTES_SCHEMA: dict[str, PolarsDType] = {
    "schema_version": pl.String,
    "instrument_id": pl.String,
    "source": pl.String,
    "reference_date": pl.Date,
    "value": VALUE_DTYPE,
    "currency": pl.String,
    "unit": pl.String,
    "price_type": pl.String,
    "is_official": pl.Boolean,
    "retrieved_at": UTC_DATETIME,
    "raw_artifact_id": pl.String,
    "ingestion_run_id": pl.String,
    "revision": pl.Int32,
    "quality_status": pl.String,
    "ticker": pl.String,
    "isin": pl.String,
    "cnpj_fundo_classe": pl.String,
    "cvm_subclass_id": pl.String,
    "title_type": pl.String,
    "maturity_date": pl.Date,
}

FUND_NAV_SCHEMA = QUOTES_SCHEMA

RATES_SCHEMA: dict[str, PolarsDType] = {
    "schema_version": pl.String,
    "series_code": pl.String,
    "source_series_id": pl.String,
    "source": pl.String,
    "name": pl.String,
    "reference_date": pl.Date,
    "value": VALUE_DTYPE,
    "unit": pl.String,
    "value_semantics": pl.String,
    "retrieved_at": UTC_DATETIME,
    "raw_artifact_id": pl.String,
    "ingestion_run_id": pl.String,
    "revision": pl.Int32,
    "quality_status": pl.String,
}

INSTRUMENTS_SCHEMA: dict[str, PolarsDType] = {
    "schema_version": pl.String,
    "instrument_id": pl.String,
    "source": pl.String,
    "asset_class": pl.String,
    "instrument_type": pl.String,
    "name": pl.String,
    "currency": pl.String,
    "exchange": pl.String,
    "mic": pl.String,
    "issuer": pl.String,
    "maturity_date": pl.Date,
    "active_from": pl.Date,
    "active_until": pl.Date,
    "ticker": pl.String,
    "isin": pl.String,
    "cnpj_fundo_classe": pl.String,
    "cvm_subclass_id": pl.String,
    "title_type": pl.String,
}

SOURCES_SCHEMA: dict[str, PolarsDType] = {
    "name": pl.String,
    "display_name": pl.String,
    "official": pl.Boolean,
    "data_license": pl.String,
    "redistribution_policy": pl.String,
    "homepage": pl.String,
    "documentation_url": pl.String,
    "attribution": pl.String,
}

CATALOG_SCHEMAS: dict[str, dict[str, PolarsDType]] = {
    "sources": SOURCES_SCHEMA,
    "instruments": INSTRUMENTS_SCHEMA,
    "quotes": QUOTES_SCHEMA,
    "fund_nav": FUND_NAV_SCHEMA,
    "rates": RATES_SCHEMA,
}

FLOAT_DTYPES = (pl.Float32, pl.Float64)


class DatasetSchemaError(ValueError):
    """Raised when a dataset frame does not match the published schema."""


def empty_frame(schema: dict[str, PolarsDType]) -> pl.DataFrame:
    return pl.DataFrame(schema=schema)


def frame_from_records(
    records: list[dict[str, object]], schema: dict[str, PolarsDType]
) -> pl.DataFrame:
    if not records:
        return empty_frame(schema)
    return pl.DataFrame(records, schema=schema)


def _is_float_dtype(dtype: PolarsDType) -> bool:
    return dtype in FLOAT_DTYPES


def validate_frame(frame: pl.DataFrame, schema: dict[str, PolarsDType]) -> None:
    expected_columns = list(schema.keys())
    actual_columns = list(frame.columns)
    if actual_columns != expected_columns:
        raise DatasetSchemaError(
            f"column mismatch: expected {expected_columns}, got {actual_columns}"
        )
    for name, expected in schema.items():
        actual = frame.schema[name]
        if _is_float_dtype(actual) or _is_float_dtype(expected):
            raise DatasetSchemaError(f"float column forbidden: {name} ({actual})")
        if actual != expected:
            raise DatasetSchemaError(
                f"dtype mismatch for {name}: expected {expected}, got {actual}"
            )
