"""Experiment specification loading and normalization."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


def _to_date_str(value: Any, field_name: str) -> str:
    """Normalize date_range.start/end to YYYY-MM-DD string (PyYAML may parse as date)."""
    if value is None:
        raise ValueError(f"'{field_name}' is required")
    if isinstance(value, str):
        s = value.strip()
        if not s:
            raise ValueError(f"'{field_name}' must be a non-empty YYYY-MM-DD string")
        return s
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    raise ValueError(f"'{field_name}' must be a YYYY-MM-DD string or date")


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

    for field in ("strategy", "symbols"):
        if field not in raw:
            raise ValueError(f"Missing required field: '{field}'")
    if "date_range" not in raw and ("start" not in raw or "end" not in raw):
        raise ValueError("Missing required field: 'date_range' or top-level 'start'/'end'")

    name = raw.get("experiment_name", spec_path.stem)
    strategy = raw["strategy"]
    symbols = raw["symbols"]
    date_range = _require_mapping(raw.get("date_range"), "date_range")
    start_value = date_range.get("start", raw.get("start"))
    end_value = date_range.get("end", raw.get("end"))

    if not isinstance(name, str) or not name.strip():
        raise ValueError("'experiment_name' must be a non-empty string")
    if not isinstance(strategy, str) or not strategy.strip():
        raise ValueError("'strategy' must be a non-empty string")
    if not isinstance(symbols, list) or not symbols or not all(isinstance(s, str) and s.strip() for s in symbols):
        raise ValueError("'symbols' must be a non-empty list of strings")

    start = _to_date_str(start_value, "start")
    end = _to_date_str(end_value, "end")

    parameters = _require_mapping(raw.get("parameters"), "parameters")
    if "grid_search" in raw and "params" in raw:
        raise ValueError("Use either 'grid_search' or 'params', not both")
    grid = _require_mapping(raw.get("grid_search", raw.get("params")), "grid_search")
    for key, values in grid.items():
        if not isinstance(values, list) or not values:
            raise ValueError(f"'grid_search.{key}' must be a non-empty list")

    execution = _require_mapping(raw.get("execution"), "execution")

    return {
        "name": name.strip(),
        "strategy": strategy.strip(),
        "symbols": [symbol.strip() for symbol in symbols],
        "start": start,
        "end": end,
        "parameters": dict(parameters),
        "grid": dict(grid),
        "execution": dict(execution),
    }
