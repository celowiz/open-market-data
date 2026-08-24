from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from marketdata.domain.enums import PriceType, QualityStatus
from marketdata.domain.errors import InvalidFinancialValueError, exact_decimal


class MarketSeries(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    name: str
    source_name: str
    source_series_id: str
    unit: str
    value_semantics: PriceType = PriceType.REFERENCE
    metadata: dict[str, object] = Field(default_factory=dict)


class MarketSeriesObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    series_code: str
    reference_date: date
    value: Decimal
    source_name: str
    unit: str
    retrieved_at: datetime | None = None
    raw_artifact_id: UUID | str | None = None
    ingestion_run_id: UUID | str | None = None
    revision: int = 1
    quality_status: QualityStatus = QualityStatus.OK
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("value", mode="before")
    @classmethod
    def reject_float(cls, value: object) -> Decimal:
        if isinstance(value, float):
            raise InvalidFinancialValueError(
                "binary float values are not allowed for financial amounts"
            )
        return exact_decimal(value)  # type: ignore[arg-type]
