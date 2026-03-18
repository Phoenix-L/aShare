"""Multi-day excursion indicator utilities."""

from __future__ import annotations

import backtrader as bt
import pandas as pd


def compute_multi_day_excursion(df: pd.DataFrame, window: int = 3) -> pd.Series:
    """Return the rolling multi-day high/low excursion ratio normalized by close.

    For each row, the indicator computes the rolling highest high and lowest low
    over ``window`` bars, measures their excursion, and normalizes the result by
    the current close price. Early rows that do not have enough history are left
    as ``NaN``.
    """
    if window <= 0:
        raise ValueError("window must be a positive integer")
    if "high" not in df.columns or "low" not in df.columns or "close" not in df.columns:
        raise ValueError("DataFrame must contain 'high', 'low', and 'close' columns")

    high_n = df["high"].rolling(window=window, min_periods=window).max()
    low_n = df["low"].rolling(window=window, min_periods=window).min()
    excursion = high_n - low_n
    return excursion.div(df["close"])


class MultiDayExcursion(bt.Indicator):
    """Backtrader line version of the multi-day excursion ratio."""

    lines = ("excursion_ratio",)
    params = (("window", 3),)

    def __init__(self) -> None:
        high_n = bt.indicators.Highest(self.data.high, period=self.p.window)
        low_n = bt.indicators.Lowest(self.data.low, period=self.p.window)
        self.lines.excursion_ratio = (high_n - low_n) / self.data.close
