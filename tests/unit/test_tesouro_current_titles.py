from datetime import date

from marketdata.config import Settings
from marketdata.ingestion.tesouro import tesouro_records_for_persist
from marketdata.providers.tesouro import tesouro_record_key

# Latest Data Base is 12/01/2025. Tesouro Prefixado (LTN:2035-01-01) trades that
# day and has history. Tesouro Selic (LFT:2026-03-01) last appears on 11/01/2025
# (matured / off-book relative to the latest day).
_HEADER = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;"
    "PU Compra Manha;PU Venda Manha;PU Base Manha"
)
CURRENT_AND_MATURED_CSV = "\n".join(
    [
        _HEADER,
        "Tesouro Prefixado;01/01/2035;10/01/2025;14,00;14,10;111,11;111,11;111,11",
        "Tesouro Prefixado;01/01/2035;11/01/2025;14,20;14,30;222,22;222,22;222,22",
        "Tesouro Prefixado;01/01/2035;12/01/2025;14,40;14,50;333,33;333,33;333,33",
        "Tesouro Selic;01/03/2026;10/01/2025;0,10;0,11;10000,00;10000,00;10000,00",
        "Tesouro Selic;01/03/2026;11/01/2025;0,12;0,13;10001,00;10001,00;10001,00",
        "",
    ]
)

CURRENT_KEY = "LTN:2035-01-01"
MATURED_KEY = "LFT:2026-03-01"
HISTORY_DATES = {date(2025, 1, 10), date(2025, 1, 11), date(2025, 1, 12)}


def _keys(records) -> set[str]:
    return {tesouro_record_key(record) for record in records}


def _dates_for(records, key: str) -> set[date]:
    return {record.reference_date for record in records if tesouro_record_key(record) == key}


def test_current_title_keeps_full_history() -> None:
    records = tesouro_records_for_persist(CURRENT_AND_MATURED_CSV, current_titles_only=True)
    assert CURRENT_KEY in _keys(records)
    assert _dates_for(records, CURRENT_KEY) == HISTORY_DATES


def test_matured_title_is_skipped() -> None:
    records = tesouro_records_for_persist(CURRENT_AND_MATURED_CSV, current_titles_only=True)
    assert MATURED_KEY not in _keys(records)
    assert all(tesouro_record_key(record) == CURRENT_KEY for record in records)


def test_flag_false_persists_full_csv_including_matured() -> None:
    records = tesouro_records_for_persist(CURRENT_AND_MATURED_CSV, current_titles_only=False)
    assert _keys(records) == {CURRENT_KEY, MATURED_KEY}
    assert _dates_for(records, CURRENT_KEY) == HISTORY_DATES
    assert _dates_for(records, MATURED_KEY) == {date(2025, 1, 10), date(2025, 1, 11)}


def test_daily_ingest_uses_full_csv_latest_day_for_live_set() -> None:
    records = tesouro_records_for_persist(
        CURRENT_AND_MATURED_CSV,
        reference_date=date(2025, 1, 11),
        current_titles_only=True,
    )
    assert _keys(records) == {CURRENT_KEY}
    assert _dates_for(records, CURRENT_KEY) == {date(2025, 1, 11)}


def test_backfill_window_still_uses_full_csv_latest_day() -> None:
    records = tesouro_records_for_persist(
        CURRENT_AND_MATURED_CSV,
        start=date(2025, 1, 10),
        end=date(2025, 1, 11),
        current_titles_only=True,
    )
    assert _keys(records) == {CURRENT_KEY}
    assert _dates_for(records, CURRENT_KEY) == {date(2025, 1, 10), date(2025, 1, 11)}


def test_tesouro_current_titles_only_defaults_true() -> None:
    settings = Settings(_env_file=None)
    assert settings.tesouro_current_titles_only is True


def test_tesouro_current_titles_only_env_false(monkeypatch) -> None:
    monkeypatch.setenv("TESOURO_CURRENT_TITLES_ONLY", "false")
    settings = Settings(_env_file=None)
    assert settings.tesouro_current_titles_only is False
