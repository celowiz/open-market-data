from pathlib import Path

from marketdata.coverage.paths import default_universe_path, named_universe_path


def test_default_universe_prefers_operator_file_when_present(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    example = config / "instruments.example.csv"
    operator = config / "instruments.csv"
    example.write_text("example\n", encoding="utf-8")
    operator.write_text("operator\n", encoding="utf-8")
    assert default_universe_path(tmp_path) == operator


def test_default_universe_falls_back_to_example(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    example = config / "instruments.example.csv"
    example.write_text("example\n", encoding="utf-8")
    assert default_universe_path(tmp_path) == example


def test_named_universe_example_and_operator(tmp_path: Path) -> None:
    assert named_universe_path("example", base=tmp_path) == (
        tmp_path / "config" / "instruments.example.csv"
    )
    assert named_universe_path("operator", base=tmp_path) == (
        tmp_path / "config" / "instruments.csv"
    )
