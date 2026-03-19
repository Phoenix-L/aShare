"""Grid search parameter expansion."""

from __future__ import annotations

from itertools import product
from typing import Any

MEAN_REVERSION_ADVANCED_KEYS = {
    "signal_mode",
    "z_entry",
    "z_exit",
    "use_atr_filter",
    "use_art_filter",
    "atr_ratio_min",
    "art_threshold",
    "use_multi_day_excursion",
    "excursion_window",
    "excursion_min",
}

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

def _uses_mean_reversion_advanced_normalization(params: dict[str, Any], strategy_name: str | None = None) -> bool:
    """Return True when excursion/zscore dedup rules should apply."""
    if strategy_name == "mean_reversion_advanced":
        return True
    return any(key in params for key in MEAN_REVERSION_ADVANCED_KEYS)

def normalize_params(params: dict[str, Any], strategy_name: str | None = None) -> dict[str, Any]:
    """Normalize dependent parameters so equivalent runs share the same representation."""
    normalized = params.copy()
    if not _uses_mean_reversion_advanced_normalization(normalized, strategy_name=strategy_name):
        return normalized

    signal_mode = normalized.get("signal_mode", "zscore")

    if signal_mode != "excursion":
        if "excursion_lookback_bars" in normalized:
            normalized["excursion_lookback_bars"] = None
        if "excursion_threshold" in normalized:
            normalized["excursion_threshold"] = None

    # Multi-day excursion is only meaningful in zscore mode. In excursion mode,
    # force it off so it can't conflict with validation inside the strategy.
    if signal_mode == "excursion":
        if "use_multi_day_excursion" in normalized:
            normalized["use_multi_day_excursion"] = False

    if signal_mode == "excursion" or not normalized.get("use_multi_day_excursion", False):
        if "excursion_min" in normalized:
            normalized["excursion_min"] = None
        if "excursion_window" in normalized:
            normalized["excursion_window"] = None

    return normalized

def dict_to_key(params: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    """Convert a parameter mapping into a stable key for deduplication."""
    return tuple(sorted(params.items()))

def deduplicate_parameter_sets(
    param_sets: list[dict[str, Any]],
    strategy_name: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize and deduplicate equivalent parameter combinations."""
    unique_map: dict[tuple[tuple[str, Any], ...], dict[str, Any]] = {}

    for params in param_sets:
        normalized = normalize_params(params, strategy_name=strategy_name)
        key = dict_to_key(normalized)
        if key not in unique_map:
            unique_map[key] = normalized

    return list(unique_map.values())

def generate_parameter_sets(payload: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate merged parameter sets from base parameters + grid dimensions."""
    parameters = dict(payload.get("parameters") or {})
    grid = dict(payload.get("grid") or {})
    strategy_name = payload.get("strategy")

    combinations = [dict(parameters, **combo) for combo in expand_grid(grid)]
    return deduplicate_parameter_sets(combinations, strategy_name=strategy_name)
