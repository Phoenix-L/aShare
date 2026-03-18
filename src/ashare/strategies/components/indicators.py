"""Reusable indicator helpers for strategy modules."""

import backtrader as bt


def compute_zscore(close: float, mean_value: float, atr: float) -> float:
    """Compute mean-reversion z-score with ATR normalization."""
    return (close - mean_value) / atr


def build_mean_reversion_indicators(data, ma_short: int, ma_trend: int, atr_period: int):
    """Create common MA/ATR indicators for mean-reversion style strategies."""
    ma_short_line = bt.indicators.SimpleMovingAverage(data.close, period=ma_short)
    ma_trend_line = bt.indicators.SimpleMovingAverage(data.close, period=ma_trend)
    atr_line = bt.indicators.ATR(data, period=atr_period)
    return ma_short_line, ma_trend_line, atr_line


def compute_atr_ratio(atr: float, price: float) -> float:
    """Compute ATR ratio as ``ATR / price`` for volatility filtering."""
    if price == 0:
        return 0.0
    return atr / price


# Backward-compatible alias for historical ART typo.
compute_art = compute_atr_ratio
