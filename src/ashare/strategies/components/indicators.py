"""Reusable indicator helpers for strategy modules."""

import backtrader as bt


def compute_zscore(close: float, mean_value: float, atr: float) -> float:
    """Compute mean-reversion z-score with ATR normalization."""
    return (close - mean_value) / atr


def build_mean_reversion_indicators(
    data,
    ma_short: int,
    ma_trend: int,
    atr_period: int,
    *,
    ma_source=None,
    atr_source=None,
):
    """
    Create common MA/ATR indicators for mean-reversion style strategies.

    Parameters
    ----------
    data:
        Primary data feed (typically intraday) used for strategy execution.
    ma_source:
        Data feed used for moving averages. If omitted, uses ``data``.
    atr_source:
        Data feed used for ATR. If omitted, uses ``data``.
    """
    # Backtrader data feeds/lines override truthiness; do not use `or` here.
    ma_data = ma_source if ma_source is not None else data
    atr_data = atr_source if atr_source is not None else data

    ma_short_line = bt.indicators.SimpleMovingAverage(ma_data.close, period=ma_short)
    ma_trend_line = bt.indicators.SimpleMovingAverage(ma_data.close, period=ma_trend)
    atr_line = bt.indicators.ATR(atr_data, period=atr_period)
    return ma_short_line, ma_trend_line, atr_line


def compute_atr_ratio(atr: float, price: float) -> float:
    """Compute ATR ratio as ``ATR / price`` for volatility filtering."""
    if price == 0:
        return 0.0
    return atr / price


# Backward-compatible alias for historical ART typo.
compute_art = compute_atr_ratio
