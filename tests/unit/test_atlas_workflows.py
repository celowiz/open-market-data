from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_b3_lending_workflow_after_eod_neon_writes_and_universe() -> None:
    text = _text("ingest-b3-lending.yml")
    assert "workflow_dispatch:" in text
    assert 'cron: "30 0 * * 2-6"' in text
    assert "group: neon-writes" in text
    assert "cancel-in-progress: false" in text
    assert "INGEST_UNIVERSE: ${{ vars.INGEST_UNIVERSE }}" in text
    assert "DATABASE_URL: ${{ secrets.DATABASE_URL }}" in text
    assert "marketdata ingest b3-lending" in text
    assert 'YAHOO_PROVIDER_ENABLED: "false"' in text
    assert "B3_PROVIDER_ENABLED" in text


def test_fred_workflow_skips_when_key_missing() -> None:
    text = _text("ingest-fred.yml")
    assert "workflow_dispatch:" in text
    assert "group: neon-writes" in text
    assert "FRED_API_KEY: ${{ secrets.FRED_API_KEY }}" in text
    assert "marketdata ingest fred" in text
    assert "FRED_PROVIDER_ENABLED" in text
    assert "FRED ingest skipped: FRED_API_KEY is not set." in text
    assert "steps.fredkey.outputs.skip != 'true'" in text


def test_optional_macro_workflows_share_neon_writes() -> None:
    for name in (
        "ingest-ibge.yml",
        "ingest-cvm-events.yml",
        "ingest-cftc.yml",
        "ingest-13f.yml",
    ):
        text = _text(name)
        assert "group: neon-writes" in text, name
        assert "cancel-in-progress: false" in text, name
        assert "DATABASE_URL: ${{ secrets.DATABASE_URL }}" in text, name
        assert 'YAHOO_PROVIDER_ENABLED: "false"' in text, name
