"""Reusable strategy components."""

from ashare.strategies.components.execution import (
    ExitDecision,
    PositionState,
    create_position_state,
    evaluate_exit_engine,
    export_trade_metrics,
    get_holding_bars,
    update_trade_metrics,
)
from ashare.strategies.components.filters import passes_art_filter, passes_atr_filter, passes_trend_filter
from ashare.strategies.components.indicators import (
    build_mean_reversion_indicators,
    compute_art,
    compute_atr_ratio,
    compute_zscore,
)
from ashare.strategies.components.shock_score import (
    DEFAULT_NOISE_LOOKBACK,
    DEFAULT_NOISE_RATIO_SCALE,
    DEFAULT_SCORE_WEIGHTS,
    DEFAULT_SPEED_SCALE,
    ShockScoreComponents,
    ShockScoreBreakdown,
    compute_shock_components,
    compute_shock_score,
    compute_weighted_score,
)

__all__ = [
    "ExitDecision",
    "PositionState",
    "create_position_state",
    "evaluate_exit_engine",
    "export_trade_metrics",
    "get_holding_bars",
    "update_trade_metrics",
    "build_mean_reversion_indicators",
    "compute_art",
    "compute_atr_ratio",
    "compute_zscore",
    "passes_art_filter",
    "passes_atr_filter",
    "passes_trend_filter",
    "DEFAULT_NOISE_LOOKBACK",
    "DEFAULT_NOISE_RATIO_SCALE",
    "DEFAULT_SCORE_WEIGHTS",
    "DEFAULT_SPEED_SCALE",
    "ShockScoreComponents",
    "ShockScoreBreakdown",
    "compute_shock_components",
    "compute_shock_score",
    "compute_weighted_score",
]
