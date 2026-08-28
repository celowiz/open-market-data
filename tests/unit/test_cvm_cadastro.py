from datetime import date
from decimal import Decimal
from pathlib import Path

from marketdata.config import Settings
from marketdata.providers.cvm import (
    CvmDailyRecord,
    cadastro_url,
    detect_schema_era,
    parse_cadastro_zip,
    parse_cvm_class_allowlist,
    parse_informe_diario,
    parse_registro_classe,
    should_persist_cvm_class,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cvm"
REGISTRO_CLASSE = (FIXTURES / "registro_classe.csv").read_text(encoding="latin-1")

MULTIMERCADO = "11111111000111"
ACOES = "22222222000122"
RENDA_FIXA = "33333333000133"
FII = "44444444000144"
FIDC = "55555555000155"
DUPLICATE = "77777777000177"
UNCLASSIFIED = "66666666000166"

SCRATCH_ALLOWLIST = frozenset({"Multimercado", "Ações"})


def _zip_csv(name: str, text: str) -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, text.encode("latin-1"))
    return buffer.getvalue()


def _daily(cnpj: str, quota: str = "1.25") -> CvmDailyRecord:
    return CvmDailyRecord(
        cnpj_fundo_classe=cnpj,
        subclass_id=None,
        reference_date=date(2026, 1, 15),
        quota_value=Decimal(quota),
        net_assets=Decimal("100.00"),
        portfolio_value=Decimal("100.00"),
        inflows=Decimal("0"),
        outflows=Decimal("0"),
        shareholder_count=1,
        schema_era="C",
        raw={},
    )


def test_cadastro_url_is_registro_fundo_classe_zip() -> None:
    url = cadastro_url()
    assert url == "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"
    assert url.endswith(".zip")
    assert "cad_fi.csv" not in url


def test_registro_classe_header_uses_official_column_names() -> None:
    header = REGISTRO_CLASSE.splitlines()[0].split(";")
    assert "CNPJ_Classe" in header
    assert "Classificacao" in header
    assert "Tipo_Classe" in header
    assert "CLASSE" not in header
    assert detect_schema_era(["CNPJ_FUNDO_CLASSE", "DT_COMPTC", "VL_QUOTA"]) == "C"


def test_parse_registro_classe_joins_on_digits_cnpj_classe() -> None:
    by_cnpj = parse_registro_classe(REGISTRO_CLASSE)
    assert by_cnpj[MULTIMERCADO].classe == "Multimercado"
    assert by_cnpj[ACOES].classe == "Ações"
    assert by_cnpj[RENDA_FIXA].classe == "Renda Fixa"
    assert by_cnpj[FII].classe is None
    assert by_cnpj[FIDC].classe is None
    assert by_cnpj[FII].tipo_classe == "Classes de Cotas de Fundos FII"
    assert by_cnpj[FIDC].tipo_classe == "Classes de Cotas de Fundos FIDC"
    assert by_cnpj[MULTIMERCADO].denominacao_social == "Fundo Multimercado Fixture"


def test_duplicate_cnpj_prefers_em_funcionamento_normal() -> None:
    by_cnpj = parse_registro_classe(REGISTRO_CLASSE)
    record = by_cnpj[DUPLICATE]
    assert record.situacao == "Em Funcionamento Normal"
    assert record.classe is None
    assert record.tipo_classe == "Classes de Cotas de Fundos FIDC"


def test_parse_cadastro_zip_reads_registro_classe_member() -> None:
    payload = _zip_csv("registro_classe.csv", REGISTRO_CLASSE)
    by_cnpj = parse_cadastro_zip(payload)
    assert ACOES in by_cnpj
    assert by_cnpj[ACOES].classe == "Ações"


def test_informe_row_joins_cadastro_on_cnpj_fundo_classe() -> None:
    by_cnpj = parse_registro_classe(REGISTRO_CLASSE)
    record = _daily(MULTIMERCADO)
    joined = by_cnpj.get(record.cnpj_fundo_classe)
    assert joined is not None
    assert joined.classe == "Multimercado"


def test_parse_informe_joins_fixture_cnpj() -> None:
    text = (
        "TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;ID_SUBCLASSE;DT_COMPTC;"
        "VL_TOTAL;VL_QUOTA;VL_PATRIM_LIQ;CAPTC_DIA;RESG_DIA;NR_COTST\n"
        "CLASSES - FIF;11.111.111/0001-11;;2026-01-15;100.00;1.25;100.00;0.00;0.00;1\n"
    )
    records = parse_informe_diario(text)
    by_cnpj = parse_registro_classe(REGISTRO_CLASSE)
    assert records[0].cnpj_fundo_classe == MULTIMERCADO
    assert by_cnpj[records[0].cnpj_fundo_classe].classe == "Multimercado"


def test_cvm_classes_unset_is_none_allowlist() -> None:
    settings = Settings(_env_file=None)
    assert settings.cvm_classes == ""
    assert parse_cvm_class_allowlist("") is None
    assert parse_cvm_class_allowlist("  ,  ") is None
    assert parse_cvm_class_allowlist("Multimercado,Ações") == SCRATCH_ALLOWLIST


def test_allowlist_keeps_multimercado_and_acoes() -> None:
    by_cnpj = parse_registro_classe(REGISTRO_CLASSE)
    assert should_persist_cvm_class(by_cnpj[MULTIMERCADO].classe, SCRATCH_ALLOWLIST) is True
    assert should_persist_cvm_class(by_cnpj[ACOES].classe, SCRATCH_ALLOWLIST) is True


def test_allowlist_skips_fii_fidc_renda_fixa() -> None:
    by_cnpj = parse_registro_classe(REGISTRO_CLASSE)
    assert should_persist_cvm_class(by_cnpj[FII].classe, SCRATCH_ALLOWLIST) is False
    assert should_persist_cvm_class(by_cnpj[FIDC].classe, SCRATCH_ALLOWLIST) is False
    assert should_persist_cvm_class(by_cnpj[RENDA_FIXA].classe, SCRATCH_ALLOWLIST) is False


def test_allowlist_skips_unclassified_when_on() -> None:
    assert should_persist_cvm_class(None, SCRATCH_ALLOWLIST) is False
    assert UNCLASSIFIED not in parse_registro_classe(REGISTRO_CLASSE)


def test_unset_allowlist_keeps_every_class_including_unclassified() -> None:
    by_cnpj = parse_registro_classe(REGISTRO_CLASSE)
    for cnpj in (MULTIMERCADO, ACOES, RENDA_FIXA, FII, FIDC):
        assert should_persist_cvm_class(by_cnpj[cnpj].classe, None) is True
    assert should_persist_cvm_class(None, None) is True
