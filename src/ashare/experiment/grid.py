"""Grid search parameter expansion."""

from __future__ import annotations

from itertools import product
from typing import Any

from ashare.strategies.validation import validate_strategy_params

SHOCK_REVERSION_INTRADAY_KEYS = {
    "excursion_lookback_bars",
    "excursion_threshold",
    "use_margin",
    "margin_rate_annual",
    "bars_per_day",
    "take_profit_pct",
    "recovery_frac",
    "max_hold_bars",
    "stop_loss_pct",
    "speed_scale",
    "noise_lookback",
    "noise_ratio_scale",
    "entry_score_weight_depth",
    "entry_score_weight_speed",
    "entry_score_weight_stabilization",
    "entry_score_weight_noise_penalty",
    "add_score_weight_depth",
    "add_score_weight_speed",
    "add_score_weight_stabilization",
    "add_score_weight_noise_penalty",
    "score_weight_depth",
    "score_weight_speed",
    "score_weight_stabilization",
    "score_weight_noise_penalty",
    "entry_shock_score_min",
    "entry_shock_score_max",
    "use_shock_score_filter",
    "shock_score_min",
    "shock_score_max",
    "enable_ladder",
    "max_legs",
    "ladder_min_drop_pct",
    "ladder_min_bars_between_legs",
    "add_score_min",
    "ladder_score_min_add",
    "min_bars_left_for_add",
}


def expand_grid(grid_dict: dict[str, list[Any]] | None) -> list[dict[str, Any]]:
    """Expand a parameter grid mapping into full cartesian product combinations."""
    if not grid_dict:
        return [{}]

    keys = list(grid_dict.keys())
    values = list(grid_dict.values())

    return [dict(zip(keys, combo)) for combo in product(*values)]


def normalize_params(params: dict[str, Any], strategy_name: str | None = None) -> dict[str, Any]:
    """Normalize dependent parameters so equivalent runs share the same representation."""
    normalized = params.copy()
    if strategy_name == "shock_reversion_intraday":
        # The strategy is excursion-only. Keep only meaningful strategy params
        # so deduplication is stable even if callers attach unrelated metadata.
        return {key: value for key, value in normalized.items() if key in SHOCK_REVERSION_INTRADAY_KEYS or key == "trade_unit"}
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

    if strategy_name:
        validate_strategy_params(strategy_name, parameters)
        validate_strategy_params(strategy_name, {key: values[0] for key, values in grid.items() if values})

    combinations = [dict(parameters, **combo) for combo in expand_grid(grid)]
    if strategy_name:
        for combo in combinations:
            validate_strategy_params(strategy_name, combo)
    return deduplicate_parameter_sets(combinations, strategy_name=strategy_name)
