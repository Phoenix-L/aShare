"""Pandas DataFrame to Backtrader feed format."""

import pandas as pd

import backtrader as bt


class PandasDataWithTurnover(bt.feeds.PandasData):
    """PandasData with optional turnover_rate line for A-share strategies."""

    lines = ("turnover_rate",)
    params = (("turnover_rate", -1),)


def to_backtrader_feed(
    df: pd.DataFrame,
    turnover_column: str = "turnover_rate",
) -> bt.feeds.PandasData:
    """
    Build a Backtrader feed from a normalized DataFrame.

    Expects index = datetime, columns: open, high, low, close, volume.
    If turnover_column exists, uses PandasDataWithTurnover so strategy can use data.turnover_rate.
    """
    if df is None or df.empty:
        raise ValueError("DataFrame is empty")

    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"DataFrame missing column: {col}")

    if turnover_column in df.columns:
        return PandasDataWithTurnover(dataname=df)
    return bt.feeds.PandasData(dataname=df)
