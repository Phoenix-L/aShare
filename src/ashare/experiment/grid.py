"""Grid search parameter expansion."""

from __future__ import annotations

from itertools import product
from typing import Any


def expand_grid(grid_dict: dict[str, list[Any]] | None) -> list[dict[str, Any]]:
    """Expand a parameter grid mapping into full cartesian product combinations."""
    if not grid_dict:
        return [{}]

    keys = list(grid_dict.keys())
    values = list(grid_dict.values())

    return [
        dict(zip(keys, combo))
        for combo in product(*values)
    ]


def normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Normalize dependent parameters so equivalent runs share the same representation."""
    normalized = params.copy()

    if not normalized.get("use_multi_day_excursion", False):
        if "excursion_min" in normalized:
            normalized["excursion_min"] = None
        if "excursion_window" in normalized:
            normalized["excursion_window"] = None

    return normalized


def dict_to_key(params: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    """Convert a parameter mapping into a stable key for deduplication."""
    return tuple(sorted(params.items()))


def deduplicate_parameter_sets(param_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize and deduplicate equivalent parameter combinations."""
    unique_map: dict[tuple[tuple[str, Any], ...], dict[str, Any]] = {}

    for params in param_sets:
        normalized = normalize_params(params)
        key = dict_to_key(normalized)
        if key not in unique_map:
            unique_map[key] = normalized

    return list(unique_map.values())


def generate_parameter_sets(payload: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate merged parameter sets from base parameters + grid dimensions."""
    parameters = dict(payload.get("parameters") or {})
    grid = dict(payload.get("grid") or {})

    combinations = [dict(parameters, **combo) for combo in expand_grid(grid)]
    return deduplicate_parameter_sets(combinations)
