from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from marketdata.domain.enums import AssetClass


class Instrument(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    asset_class: AssetClass
    instrument_type: str
    name: str
    currency: str | None = None
    exchange: str | None = None
    mic: str | None = None
    issuer: str | None = None
    maturity_date: date | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
