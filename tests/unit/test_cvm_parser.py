from datetime import date
from decimal import Decimal
from pathlib import Path

from marketdata.providers.cvm import (
    detect_schema_era,
    extract_csv_from_zip,
    months_covering,
    parse_informe_diario,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cvm"


def test_detect_eras() -> None:
    assert detect_schema_era(["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"]) == "A"
    assert detect_schema_era(["TP_FUNDO", "CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"]) == "B"
    assert (
        detect_schema_era(
            ["TP_FUNDO_CLASSE", "CNPJ_FUNDO_CLASSE", "ID_SUBCLASSE", "DT_COMPTC", "VL_QUOTA"]
        )
        == "C"
    )


def test_parse_era_c_quota() -> None:
    text = (FIXTURES / "era_c.csv").read_text(encoding="latin-1")
    records = parse_informe_diario(text)
    assert len(records) == 1
    record = records[0]
    assert record.cnpj_fundo_classe == "00017024000153"
    assert record.subclass_id is None
    assert record.reference_date == date(2026, 8, 3)
    assert record.quota_value == Decimal("44.275588000000")
    assert record.schema_era == "C"


def test_parse_era_a_and_b() -> None:
    era_a = parse_informe_diario((FIXTURES / "era_a.csv").read_text(encoding="latin-1"))
    era_b = parse_informe_diario((FIXTURES / "era_b.csv").read_text(encoding="latin-1"))
    assert era_a[0].schema_era == "A"
    assert era_b[0].schema_era == "B"
    assert era_a[0].quota_value == Decimal("9.25")
    assert era_b[0].quota_value == Decimal("10.5")


def test_extract_csv_from_zip() -> None:
    import io
    import zipfile

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("inf_diario_fi_202608.csv", (FIXTURES / "era_c.csv").read_bytes())
    text = extract_csv_from_zip(payload.getvalue())
    assert "VL_QUOTA" in text


def test_months_covering_includes_lookback() -> None:
    months = months_covering(date(2026, 8, 21), 90)
    assert months[0] == (2026, 5)
    assert months[-1] == (2026, 8)
