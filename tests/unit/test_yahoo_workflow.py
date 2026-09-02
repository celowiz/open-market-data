from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_ingest_yahoo_workflow_enables_provider_midnight_brt_cron_and_neon_writes() -> None:
    text = (WORKFLOWS / "ingest-yahoo.yml").read_text(encoding="utf-8")
    assert 'YAHOO_PROVIDER_ENABLED: "true"' in text
    assert 'cron: "0 3 * * *"' in text
    assert "00:00 America/Sao_Paulo" in text
    assert "UTC-3" in text
    assert "workflow_dispatch:" in text
    assert "group: neon-writes" in text
    assert "cancel-in-progress: false" in text
    assert "date -u" not in text
    assert "yahoo_ingest_reference_date" in text
    assert "INGEST_UNIVERSE: ${{ vars.INGEST_UNIVERSE }}" in text
    assert "B3_EQUITY_UNIVERSE_PATH: ${{ vars.B3_EQUITY_UNIVERSE_PATH }}" in text


def test_official_ingest_and_backfill_keep_yahoo_disabled() -> None:
    for name in (
        "ingest-b3.yml",
        "ingest-bcb.yml",
        "ingest-cvm.yml",
        "ingest-tesouro.yml",
        "ingest-all.yml",
        "backfill.yml",
        "ingest-b3-lending.yml",
        "ingest-fred.yml",
        "ingest-ibge.yml",
        "ingest-cvm-events.yml",
        "ingest-cftc.yml",
        "ingest-13f.yml",
    ):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert 'YAHOO_PROVIDER_ENABLED: "false"' in text, name


def test_official_provider_crons_remain_enabled() -> None:
    assert "schedule:" in (WORKFLOWS / "ingest-b3.yml").read_text(encoding="utf-8")
    assert "schedule:" in (WORKFLOWS / "ingest-bcb.yml").read_text(encoding="utf-8")
    assert "schedule:" in (WORKFLOWS / "ingest-tesouro.yml").read_text(encoding="utf-8")


def test_ingest_cvm_has_no_daily_cron() -> None:
    text = (WORKFLOWS / "ingest-cvm.yml").read_text(encoding="utf-8")
    on_block = text.split("\njobs:", 1)[0]
    assert "workflow_dispatch:" in on_block
    assert "schedule:" not in on_block


def test_publish_datasets_workflow_skips_when_object_storage_is_not_s3() -> None:
    text = (WORKFLOWS / "publish-datasets.yml").read_text(encoding="utf-8")
    assert "schedule:" in text
    assert "OBJECT_STORAGE_BACKEND" in text
    assert "s3" in text
    assert "skipped" in text.lower() or "skip" in text.lower()
    assert "R2" in text or "r2" in text
