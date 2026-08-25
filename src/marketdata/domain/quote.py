from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from marketdata.domain.enums import (
    PUBLIC_DATASET_POLICIES,
    PriceType,
    QualityStatus,
    RedistributionPolicy,
)
from marketdata.domain.errors import exact_decimal


class Source(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str
    official: bool
    redistribution_policy: RedistributionPolicy
    ingestion_enabled: bool = True
    public_api_enabled: bool = False
    public_dataset_enabled: bool = False
    data_license: str | None = None
    homepage: str | None = None
    documentation_url: str | None = None
    notes: str | None = None

    def allows_public_api(self) -> bool:
        return self.public_api_enabled

    def allows_public_dataset(self) -> bool:
        return self.public_dataset_enabled and self.redistribution_policy in PUBLIC_DATASET_POLICIES


class InstrumentQuote(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: UUID | str
    reference_date: date
    value: Decimal
    price_type: PriceType
    source_name: str
    currency: str | None = None
    unit: str | None = None
    is_official: bool = False
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
            from marketdata.domain.errors import InvalidFinancialValueError

            raise InvalidFinancialValueError(
                "binary float values are not allowed for financial amounts"
            )
        return exact_decimal(value)  # type: ignore[arg-type]
