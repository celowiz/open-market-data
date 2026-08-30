from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile"
EXAMPLE_CSV = ROOT / "config" / "instruments.example.csv"
SCRATCH_CSV = ROOT / "config" / "instruments.scratch.csv"


def test_runtime_dockerfile_copies_example_universe_config() -> None:
    """GET /v1/coverage?universe=example needs config/ in the image WORKDIR /app."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    runtime = text.split("AS runtime", 1)[1]
    copy_config = [
        line.strip()
        for line in runtime.splitlines()
        if line.strip().startswith("COPY") and "config" in line.split()
    ]
    assert copy_config, "runtime image must COPY config/ (coverage universe CSV)"
    assert EXAMPLE_CSV.is_file()
    assert "test -f /app/config/instruments.example.csv" in runtime


def test_runtime_dockerfile_copies_scratch_universe_config() -> None:
    """GET /v1/coverage?universe=scratch needs the committed IBOV/SMLL/futures CSV."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    runtime = text.split("AS runtime", 1)[1]
    assert SCRATCH_CSV.is_file()
    assert "test -f /app/config/instruments.scratch.csv" in runtime
