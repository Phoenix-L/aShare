"""Experiment specification loading and normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REQUIRED_TOP_LEVEL_FIELDS = ("experiment_name", "strategy", "symbols", "date_range")


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"'{field_name}' must be a mapping")
    return value


def load_experiment_spec(path: str | Path) -> dict[str, Any]:
    """Load and validate experiment YAML specification."""
    spec_path = Path(path)
    if not spec_path.exists():
        raise FileNotFoundError(f"Experiment spec not found: {spec_path}")

    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Experiment spec must be a YAML mapping")

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in raw:
            raise ValueError(f"Missing required field: '{field}'")

    name = raw["experiment_name"]
    strategy = raw["strategy"]
    symbols = raw["symbols"]
    date_range = _require_mapping(raw.get("date_range"), "date_range")

    if not isinstance(name, str) or not name.strip():
        raise ValueError("'experiment_name' must be a non-empty string")
    if not isinstance(strategy, str) or not strategy.strip():
        raise ValueError("'strategy' must be a non-empty string")
    if not isinstance(symbols, list) or not symbols or not all(isinstance(s, str) and s.strip() for s in symbols):
        raise ValueError("'symbols' must be a non-empty list of strings")

    start = date_range.get("start")
    end = date_range.get("end")
    if not isinstance(start, str) or not start.strip():
        raise ValueError("'date_range.start' must be a non-empty YYYY-MM-DD string")
    if not isinstance(end, str) or not end.strip():
        raise ValueError("'date_range.end' must be a non-empty YYYY-MM-DD string")

    parameters = _require_mapping(raw.get("parameters"), "parameters")
    grid = _require_mapping(raw.get("grid_search"), "grid_search")
    for key, values in grid.items():
        if not isinstance(values, list) or not values:
            raise ValueError(f"'grid_search.{key}' must be a non-empty list")

    execution = _require_mapping(raw.get("execution"), "execution")

    return {
        "name": name.strip(),
        "strategy": strategy.strip(),
        "symbols": [symbol.strip() for symbol in symbols],
        "start": start.strip(),
        "end": end.strip(),
        "parameters": dict(parameters),
        "grid": dict(grid),
        "execution": dict(execution),
    }
