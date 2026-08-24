from enum import StrEnum


class PriceType(StrEnum):
    CLOSE = "CLOSE"
    LAST = "LAST"
    LAST_TRADE = "LAST_TRADE"
    OFFICIAL_SETTLEMENT = "OFFICIAL_SETTLEMENT"
    ADJUSTMENT = "ADJUSTMENT"
    PU_BASE = "PU_BASE"
    FUND_NAV = "FUND_NAV"
    INDICATIVE = "INDICATIVE"
    BID_PU = "BID_PU"
    ASK_PU = "ASK_PU"
    YIELD = "YIELD"
    REFERENCE = "REFERENCE"


class RedistributionPolicy(StrEnum):
    PUBLIC = "PUBLIC"
    PUBLIC_WITH_ATTRIBUTION = "PUBLIC_WITH_ATTRIBUTION"
    API_ONLY = "API_ONLY"
    INTERNAL_ONLY = "INTERNAL_ONLY"
    NO_REDISTRIBUTION = "NO_REDISTRIBUTION"
    UNKNOWN = "UNKNOWN"


class AssetClass(StrEnum):
    EQUITY = "equity"
    FUND = "fund"
    GOVERNMENT_BOND = "government_bond"
    FUTURE = "future"
    OPTION = "option"
    FX = "fx"
    RATE = "rate"
    CREDIT = "credit"
    OTHER = "other"


class IdentifierType(StrEnum):
    TICKER = "TICKER"
    ISIN = "ISIN"
    CUSIP = "CUSIP"
    CNPJ = "CNPJ"
    CNPJ_FUNDO_CLASSE = "CNPJ_FUNDO_CLASSE"
    CVM_SUBCLASS_ID = "CVM_SUBCLASS_ID"
    B3_SECURITY_ID = "B3_SECURITY_ID"
    YAHOO_SYMBOL = "YAHOO_SYMBOL"
    TITLE_TYPE = "TITLE_TYPE"
    SOURCE_ID = "SOURCE_ID"


class QualityStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    REJECTED = "rejected"


class QualitySeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class IngestionRunStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


PUBLIC_REDISTRIBUTION_POLICIES = frozenset(
    {
        RedistributionPolicy.PUBLIC,
        RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        RedistributionPolicy.API_ONLY,
    }
)

PUBLIC_DATASET_POLICIES = frozenset(
    {
        RedistributionPolicy.PUBLIC,
        RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
    }
)
