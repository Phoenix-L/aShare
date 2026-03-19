"""Strategy parameter validation helpers."""

from __future__ import annotations

from typing import Any

from ashare.strategies import get_strategy_class

FORBIDDEN_PARAMS_BY_STRATEGY: dict[str, dict[str, str]] = {
    "mean_reversion_advanced": {
        "signal_mode": "MeanReversionAdvanced is z-score only and does not accept signal_mode.",
        "use_multi_day_excursion": "MeanReversionAdvanced does not accept excursion filter params: use_multi_day_excursion.",
        "excursion_window": "MeanReversionAdvanced does not accept excursion filter params: excursion_window.",
        "excursion_min": "MeanReversionAdvanced does not accept excursion filter params: excursion_min.",
        "excursion_lookback_bars": "MeanReversionAdvanced does not accept excursion signal params: excursion_lookback_bars.",
        "excursion_threshold": "MeanReversionAdvanced does not accept excursion signal params: excursion_threshold.",
    },
    "shock_reversion_intraday": {
        "z_entry": "ShockReversionIntradayStrategy does not accept z-score params: z_entry.",
        "z_exit": "ShockReversionIntradayStrategy does not accept z-score params: z_exit.",
        "exit_mode": "ShockReversionIntradayStrategy always uses recovery + take-profit + stop-loss + max-hold exits; exit_mode is not supported.",
        "signal_mode": "ShockReversionIntradayStrategy is excursion-only and does not accept signal_mode.",
        "use_multi_day_excursion": "ShockReversionIntradayStrategy does not accept legacy excursion filter params: use_multi_day_excursion.",
        "excursion_window": "ShockReversionIntradayStrategy does not accept legacy excursion filter params: excursion_window.",
        "excursion_min": "ShockReversionIntradayStrategy does not accept legacy excursion filter params: excursion_min.",
        "use_atr_filter": "ShockReversionIntradayStrategy does not accept ATR gate params: use_atr_filter.",
        "use_art_filter": "ShockReversionIntradayStrategy does not accept ATR gate params: use_art_filter.",
        "atr_ratio_min": "ShockReversionIntradayStrategy does not accept ATR gate params: atr_ratio_min.",
        "art_threshold": "ShockReversionIntradayStrategy does not accept ATR gate params: art_threshold.",
    },
}


def _strategy_default_params(strategy_cls) -> dict[str, Any]:
    defaults = strategy_cls.params
    if hasattr(defaults, "_getitems"):
        return dict(defaults._getitems())
    if isinstance(defaults, dict):
        return dict(defaults)
    if isinstance(defaults, tuple):
        return dict(defaults)
    return {}


def validate_strategy_params(strategy_name: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """Validate parameter names for the selected strategy and fail fast on forbidden keys."""
    normalized = dict(params or {})
    try:
        strategy_cls = get_strategy_class(strategy_name)
    except KeyError:
        return normalized
    defaults = _strategy_default_params(strategy_cls)
    forbidden = FORBIDDEN_PARAMS_BY_STRATEGY.get(strategy_name, {})

    forbidden_keys = [key for key in normalized if key in forbidden]
    if forbidden_keys:
        details = "; ".join(forbidden[key] for key in sorted(forbidden_keys))
        raise ValueError(f"Invalid config for {strategy_name}: {details}")

    unsupported = sorted(key for key in normalized if key not in defaults)
    if unsupported:
        allowed = ", ".join(sorted(defaults))
        raise ValueError(
            f"Invalid config for {strategy_name}: unsupported params {unsupported}. Allowed params: {allowed}"
        )

    return normalized
