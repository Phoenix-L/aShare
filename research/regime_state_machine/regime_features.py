"""Feature engineering utilities for deterministic market-regime research.

This module intentionally focuses on simple, interpretable rolling features
built from OHLCV data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"datetime", "open", "high", "low", "close", "volume"}


@dataclass(frozen=True)
class FeatureConfig:
    """Configuration for rolling regime features."""

    equilibrium_window_short: int = 20
    equilibrium_window_long: int = 40
    trend_window: int = 20
    persistence_window: int = 20
    snapback_threshold: float = 0.02
    reset_band: float = 0.005
    snapback_horizon: int = 10
    snapback_lookback: int = 80


def validate_ohlcv(df: pd.DataFrame) -> None:
    """Raise if the dataframe does not contain required OHLCV columns."""

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")


def _same_sign_fraction(returns: pd.Series, window: int) -> pd.Series:
    signs = np.sign(returns)
    same = (signs * signs.shift(1) > 0).astype(float)
    return same.rolling(window=window, min_periods=max(5, window // 4)).mean()


def _sign_autocorr(returns: pd.Series, window: int) -> pd.Series:
    signs = np.sign(returns)

    def autocorr_fn(values: np.ndarray) -> float:
        if len(values) < 2:
            return np.nan
        x = values[:-1]
        y = values[1:]
        if np.all(x == x[0]) or np.all(y == y[0]):
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])

    return signs.rolling(window=window, min_periods=max(5, window // 4)).apply(autocorr_fn, raw=True)


def _compute_snapback_events(
    distance: pd.Series,
    threshold: float,
    reset_band: float,
    horizon: int,
) -> pd.DataFrame:
    excursion = distance.abs() >= threshold
    success = pd.Series(False, index=distance.index)

    # A simple event-style pass to evaluate re-entry into reset band in H bars.
    indices = np.flatnonzero(excursion.values)
    for i in indices:
        end = min(i + horizon, len(distance) - 1)
        future = distance.iloc[i + 1 : end + 1]
        if future.empty:
            continue
        if (future.abs() <= reset_band).any():
            success.iloc[i] = True

    return pd.DataFrame(
        {
            "excursion_flag": excursion.astype(int),
            "snapback_success_flag": success.astype(int),
        },
        index=distance.index,
    )


def compute_regime_features(df: pd.DataFrame, config: FeatureConfig | None = None) -> pd.DataFrame:
    """Compute interpretable rolling features used by regime classification."""

    cfg = config or FeatureConfig()
    validate_ohlcv(df)

    out = df.copy()
    out = out.sort_values("datetime").reset_index(drop=True)
    out["datetime"] = pd.to_datetime(out["datetime"])

    out["equilibrium_short"] = out["close"].rolling(
        window=cfg.equilibrium_window_short,
        min_periods=max(5, cfg.equilibrium_window_short // 4),
    ).mean()
    out["equilibrium_long"] = out["close"].rolling(
        window=cfg.equilibrium_window_long,
        min_periods=max(8, cfg.equilibrium_window_long // 4),
    ).mean()
    out["equilibrium"] = 0.5 * out["equilibrium_short"] + 0.5 * out["equilibrium_long"]

    out["distance_from_equilibrium"] = (out["close"] - out["equilibrium"]) / out["equilibrium"]

    net_move = (out["close"] - out["close"].shift(cfg.trend_window)).abs()
    path_len = out["close"].diff().abs().rolling(
        window=cfg.trend_window,
        min_periods=max(5, cfg.trend_window // 4),
    ).sum()
    out["trend_efficiency"] = net_move / path_len.replace(0, np.nan)
    out["trend_efficiency"] = out["trend_efficiency"].clip(lower=0.0, upper=1.0)

    returns = out["close"].pct_change()
    out["same_sign_return_fraction"] = _same_sign_fraction(returns=returns, window=cfg.persistence_window)
    out["sign_autocorr"] = _sign_autocorr(returns=returns, window=cfg.persistence_window)
    out["persistence"] = (0.5 * out["same_sign_return_fraction"] + 0.5 * (out["sign_autocorr"] + 1.0) / 2.0).clip(
        lower=0.0,
        upper=1.0,
    )

    snapback = _compute_snapback_events(
        distance=out["distance_from_equilibrium"],
        threshold=cfg.snapback_threshold,
        reset_band=cfg.reset_band,
        horizon=cfg.snapback_horizon,
    )
    out = out.join(snapback)

    excursion_rolling = out["excursion_flag"].rolling(
        window=cfg.snapback_lookback,
        min_periods=max(10, cfg.snapback_lookback // 5),
    ).sum()
    success_rolling = out["snapback_success_flag"].rolling(
        window=cfg.snapback_lookback,
        min_periods=max(10, cfg.snapback_lookback // 5),
    ).sum()
    out["snapback_rate"] = success_rolling / excursion_rolling.replace(0, np.nan)

    return out
