"""Pandas DataFrame to Backtrader feed format."""

import pandas as pd
import re

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

    def _infer_timeframe_compression(index: pd.DatetimeIndex) -> tuple[bt.TimeFrame | None, int | None]:
        """Infer Backtrader timeframe/compression from an equally-spaced DatetimeIndex."""
        if index is None or len(index) < 2:
            return None, None

        # Prefer inferred_freq when available (e.g. "30min", "D").
        inferred = getattr(index, "inferred_freq", None)
        if inferred:
            # Common cases: "30min", "5min", "D", "1D"
            m = re.match(r"^(\d+)\s*min", str(inferred), flags=re.IGNORECASE)
            if m:
                return bt.TimeFrame.Minutes, int(m.group(1))
            if str(inferred).upper() in {"D", "1D"}:
                return bt.TimeFrame.Days, 1
            # Handle "1440min" etc.
            m = re.match(r"^(\d+)\s*min$", str(inferred), flags=re.IGNORECASE)
            if m:
                minutes = int(m.group(1))
                if minutes % (24 * 60) == 0:
                    return bt.TimeFrame.Days, minutes // (24 * 60)
                return bt.TimeFrame.Minutes, minutes

        # Fallback: estimate delta between first two rows.
        delta_min = (index[1] - index[0]).total_seconds() / 60.0
        if delta_min <= 0:
            return None, None

        # If it matches whole minutes, use Minutes timeframe.
        rounded = int(round(delta_min))
        if abs(delta_min - rounded) < 1e-6:
            if rounded % (24 * 60) == 0:
                return bt.TimeFrame.Days, rounded // (24 * 60)
            return bt.TimeFrame.Minutes, rounded

        return None, None

    kwargs: dict[str, object] = {"dataname": df}
    if name:
        kwargs["name"] = name

    timeframe, compression = _infer_timeframe_compression(df.index)  # type: ignore[arg-type]
    if timeframe is not None and compression is not None:
        kwargs["timeframe"] = timeframe
        kwargs["compression"] = compression

    if turnover_column in df.columns:
        return PandasDataWithTurnover(**kwargs)
    return bt.feeds.PandasData(**kwargs)
