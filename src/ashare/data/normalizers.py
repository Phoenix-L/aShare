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
    name: str | None = None,
) -> bt.feeds.PandasData:
    """
    Build a Backtrader feed from a normalized DataFrame.

    Expects index = datetime, columns: open, high, low, close, volume.
    If turnover_column exists, uses PandasDataWithTurnover so strategy can use data.turnover_rate.

    Parameters
    ----------
    df : pd.DataFrame
        Normalized DataFrame with datetime index and OHLCV columns
    turnover_column : str
        Name of turnover rate column (default: "turnover_rate")
    name : str, optional
        Symbol name to attach to the feed (for logging/identification)
    """
    if df is None or df.empty:
        raise ValueError("DataFrame is empty")

    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"DataFrame missing column: {col}")

    kwargs = {"dataname": df}
    if name:
        kwargs["name"] = name

    if turnover_column in df.columns:
        return PandasDataWithTurnover(**kwargs)
    return bt.feeds.PandasData(**kwargs)
