"""Experiment specification loading and normalization."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


_LADDER_PARAM_MAP = {
    "enabled": "enable_ladder",
    "max_legs": "max_legs",
    "ladder_min_drop_pct": "ladder_min_drop_pct",
    "ladder_min_bars_between_legs": "ladder_min_bars_between_legs",
    "add_score_min": "add_score_min",
    "ladder_score_min_add": "ladder_score_min_add",
    "min_bars_left_for_add": "min_bars_left_for_add",
}

_SHOCK_SCORE_PARAM_MAP = {
    "excursion_lookback_bars": "excursion_lookback_bars",
    "excursion_threshold": "excursion_threshold",
    "speed_scale": "speed_scale",
    "noise_lookback": "noise_lookback",
    "noise_ratio_scale": "noise_ratio_scale",
}
_SHOCK_SCORE_WEIGHT_PARAM_MAP = {
    "entry_weights": {
        "depth": "entry_score_weight_depth",
        "speed": "entry_score_weight_speed",
        "stabilization": "entry_score_weight_stabilization",
        "noise_penalty": "entry_score_weight_noise_penalty",
    },
    "add_weights": {
        "depth": "add_score_weight_depth",
        "speed": "add_score_weight_speed",
        "stabilization": "add_score_weight_stabilization",
        "noise_penalty": "add_score_weight_noise_penalty",
    },
}
_ENTRY_PARAM_MAP = {
    "entry_shock_score_min": "entry_shock_score_min",
    "entry_shock_score_max": "entry_shock_score_max",
    "shock_score_min": "entry_shock_score_min",
    "shock_score_max": "entry_shock_score_max",
}


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


def _flatten_ladder_block(mapping: dict[str, Any], field_name: str) -> dict[str, Any]:
    normalized = dict(mapping)
    ladder = normalized.pop("ladder", None)
    if ladder is None:
        return normalized
    if not isinstance(ladder, dict):
        raise ValueError(f"'{field_name}.ladder' must be a mapping")

    for key, value in ladder.items():
        flat_key = _LADDER_PARAM_MAP.get(key)
        if flat_key is None:
            raise ValueError(f"Unsupported ladder key in '{field_name}.ladder': {key}")
        normalized[flat_key] = value
    return normalized


def _flatten_shock_score_block(mapping: dict[str, Any], field_name: str) -> dict[str, Any]:
    normalized = dict(mapping)
    shock_score = normalized.pop("shock_score", None)
    if shock_score is None:
        return normalized
    if not isinstance(shock_score, dict):
        raise ValueError(f"'{field_name}.shock_score' must be a mapping")

    for key, value in shock_score.items():
        if key in _SHOCK_SCORE_PARAM_MAP:
            normalized[_SHOCK_SCORE_PARAM_MAP[key]] = value
            continue
        if key not in _SHOCK_SCORE_WEIGHT_PARAM_MAP:
            raise ValueError(f"Unsupported shock_score key in '{field_name}.shock_score': {key}")
        if not isinstance(value, dict):
            raise ValueError(f"'{field_name}.shock_score.{key}' must be a mapping")
        for weight_key, weight_value in value.items():
            flat_key = _SHOCK_SCORE_WEIGHT_PARAM_MAP[key].get(weight_key)
            if flat_key is None:
                raise ValueError(f"Unsupported shock_score weight key in '{field_name}.shock_score.{key}': {weight_key}")
            normalized[flat_key] = weight_value

    return normalized


def _flatten_entry_block(mapping: dict[str, Any], field_name: str) -> dict[str, Any]:
    normalized = dict(mapping)
    entry = normalized.pop("entry", None)
    if entry is None:
        return normalized
    if not isinstance(entry, dict):
        raise ValueError(f"'{field_name}.entry' must be a mapping")

    for key, value in entry.items():
        flat_key = _ENTRY_PARAM_MAP.get(key)
        if flat_key is None:
            raise ValueError(f"Unsupported entry key in '{field_name}.entry': {key}")
        normalized[flat_key] = value
    return normalized


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

    parameters = _flatten_entry_block(
        _flatten_shock_score_block(
            _flatten_ladder_block(_require_mapping(raw.get("parameters"), "parameters"), "parameters"),
            "parameters",
        ),
        "parameters",
    )
    if "grid_search" in raw and "params" in raw:
        raise ValueError("Use either 'grid_search' or 'params', not both")
    grid = _flatten_entry_block(
        _flatten_shock_score_block(
            _flatten_ladder_block(_require_mapping(raw.get("grid_search", raw.get("params")), "grid_search"), "grid_search"),
            "grid_search",
        ),
        "grid_search",
    )
    for key, values in grid.items():
        if not isinstance(values, list) or not values:
            raise ValueError(f"'grid_search.{key}' must be a non-empty list")

    execution = _require_mapping(raw.get("execution"), "execution")

    return {
        "name": name.strip(),
        "output_name": spec_path.stem,
        "strategy": strategy.strip(),
        "symbols": [symbol.strip() for symbol in symbols],
        "start": start,
        "end": end,
        "parameters": dict(parameters),
        "grid": dict(grid),
        "execution": dict(execution),
    }
