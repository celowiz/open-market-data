from pathlib import Path

EXAMPLE_UNIVERSE = "example"
OPERATOR_UNIVERSE = "operator"


def default_universe_path(base: Path | None = None) -> Path:
    root = base if base is not None else Path.cwd()
    operator = root / "config" / "instruments.csv"
    if operator.is_file():
        return operator
    return root / "config" / "instruments.example.csv"


def named_universe_path(name: str, *, base: Path | None = None) -> Path:
    root = base if base is not None else Path.cwd()
    if name == EXAMPLE_UNIVERSE:
        return root / "config" / "instruments.example.csv"
    if name == OPERATOR_UNIVERSE:
        return root / "config" / "instruments.csv"
    raise ValueError(f"unknown universe: {name}")
