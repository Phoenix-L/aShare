"""Minute and daily data loaders for A-shares."""

import pandas as pd

from ashare.data.providers import get_provider


_REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume", "turnover_rate"]


def _validate_loaded_frame(df: pd.DataFrame, *, source: str) -> pd.DataFrame:
    """Validate provider output schema for downstream backtests."""
    if df is None or df.empty:
        raise ValueError(f"{source} returned no data")

    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"{source} missing required columns: {', '.join(missing)}")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"{source} index must be DatetimeIndex")

    if not df.index.is_monotonic_increasing:
        df = df.sort_index()

    return df


def load_minute_30(
    ts_code: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Load 30-minute OHLCV data with turnover_rate.

    Returns
    -------
    pandas.DataFrame
        Indexed by datetime with columns:
        open, high, low, close, volume, turnover_rate
    """
    provider = get_provider()
    df = provider.fetch_minute30(ts_code, start_date, end_date)
    return _validate_loaded_frame(df, source="fetch_minute30")


def load_daily(
    ts_code: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Load daily OHLCV data with turnover_rate.

    Returns
    -------
    pandas.DataFrame
        Indexed by datetime with columns:
        open, high, low, close, volume, turnover_rate
    """
    provider = get_provider()
    df = provider.fetch_daily(ts_code, start_date, end_date)
    return _validate_loaded_frame(df, source="fetch_daily")
