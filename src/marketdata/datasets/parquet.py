from hashlib import sha256
from io import BytesIO

import polars as pl

from marketdata.datasets.schema import FLOAT_DTYPES, DatasetSchemaError


def write_parquet_bytes(frame: pl.DataFrame) -> bytes:
    buffer = BytesIO()
    frame.write_parquet(buffer)
    return buffer.getvalue()


def sha256_hex(data: bytes) -> str:
    return sha256(data).hexdigest()


def assert_value_not_float(frame: pl.DataFrame, column: str = "value") -> None:
    dtype = frame.schema[column]
    if dtype in FLOAT_DTYPES:
        raise DatasetSchemaError(f"value column used a binary float dtype: {dtype}")
    if dtype not in (pl.String, pl.Utf8) and not _is_decimal(dtype):
        raise DatasetSchemaError(f"value column must be Decimal or Utf8 string, got {dtype}")


def _is_decimal(dtype: pl.DataType) -> bool:
    return isinstance(dtype, pl.Decimal) or dtype == pl.Decimal(38, 16)
