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


def generate_parameter_sets(payload: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate merged parameter sets from base parameters + grid dimensions."""
    parameters = dict(payload.get("parameters") or {})
    grid = dict(payload.get("grid") or {})

    combinations = expand_grid(grid)
    return [dict(parameters, **combo) for combo in combinations]
