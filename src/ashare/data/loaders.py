"""Minute and daily data loaders for A-shares."""

import pandas as pd

from ashare.data.providers import get_provider

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
    return provider.fetch_minute30(ts_code, start_date, end_date)


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
    return provider.fetch_daily(ts_code, start_date, end_date)
    
