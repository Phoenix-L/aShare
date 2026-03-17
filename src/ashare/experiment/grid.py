"""Grid search parameter expansion."""

from __future__ import annotations

from itertools import product
from typing import Any


def generate_parameter_sets(payload: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate merged parameter sets from base parameters + grid dimensions."""
    parameters = dict(payload.get("parameters") or {})
    grid = dict(payload.get("grid") or {})

    if not grid:
        return [parameters]

    keys = list(grid.keys())
    value_lists = [grid[key] for key in keys]

    combinations: list[dict[str, Any]] = []
    for combo in product(*value_lists):
        merged = dict(parameters)
        merged.update(dict(zip(keys, combo)))
        combinations.append(merged)

    return combinations
