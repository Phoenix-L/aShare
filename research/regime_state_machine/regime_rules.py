"""Deterministic regime state machine rules.

States:
- Oscillating
- Transition
- Trending
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


OSCILLATING = "Oscillating"
TRANSITION = "Transition"
TRENDING = "Trending"


@dataclass(frozen=True)
class RuleConfig:
    trend_eff_low: float = 0.35
    trend_eff_high: float = 0.60
    persistence_low: float = 0.45
    persistence_high: float = 0.60
    distance_low: float = 0.01
    distance_high: float = 0.02
    snapback_high: float = 0.60
    snapback_low: float = 0.40
    dwell_bars: int = 3


def _row_state(row: pd.Series, cfg: RuleConfig) -> str:
    te = row["trend_efficiency"]
    ps = row["persistence"]
    dist = abs(row["distance_from_equilibrium"])
    sb = row["snapback_rate"]

    if pd.isna(te) or pd.isna(ps) or pd.isna(dist) or pd.isna(sb):
        return TRANSITION

    is_osc = (
        te <= cfg.trend_eff_low
        and ps <= cfg.persistence_low
        and sb >= cfg.snapback_high
        and dist <= cfg.distance_high
    )
    is_trend = (
        te >= cfg.trend_eff_high
        and ps >= cfg.persistence_high
        and dist >= cfg.distance_high
        and sb <= cfg.snapback_low
    )

    if is_osc:
        return OSCILLATING
    if is_trend:
        return TRENDING
    return TRANSITION


def classify_regime_states(feature_df: pd.DataFrame, config: RuleConfig | None = None) -> pd.DataFrame:
    """Apply deterministic rule stack + hysteresis to generate states and events."""

    cfg = config or RuleConfig()
    out = feature_df.copy().reset_index(drop=True)

    base_states = out.apply(_row_state, axis=1, cfg=cfg)

    states: list[str] = []
    active_state = TRANSITION
    candidate_state = TRANSITION
    candidate_count = 0

    for base_state in base_states:
        if base_state == active_state:
            candidate_state = active_state
            candidate_count = 0
            states.append(active_state)
            continue

        if base_state == candidate_state:
            candidate_count += 1
        else:
            candidate_state = base_state
            candidate_count = 1

        if candidate_count >= cfg.dwell_bars:
            active_state = candidate_state
            candidate_count = 0

        states.append(active_state)

    out["base_regime_state"] = base_states
    out["regime_state"] = states
    out["prev_regime_state"] = out["regime_state"].shift(1)
    out["transition_signal"] = (
        (out["prev_regime_state"] == OSCILLATING) & (out["regime_state"] == TRANSITION)
    ) | (
        (out["prev_regime_state"] == TRANSITION) & (out["regime_state"] == TRENDING)
    )
    out["transition_signal"] = out["transition_signal"].fillna(False)

    return out


def extract_transition_events(classified_df: pd.DataFrame) -> pd.DataFrame:
    """Extract compact event table for true state changes."""

    changes = classified_df[classified_df["regime_state"] != classified_df["regime_state"].shift(1)].copy()
    changes = changes.assign(
        from_state=changes["regime_state"].shift(1),
        to_state=changes["regime_state"],
    )
    return changes[["datetime", "close", "from_state", "to_state", "transition_signal"]].reset_index(drop=True)
