"""Minute and daily data loaders for A-shares."""

from __future__ import annotations

import os

import pandas as pd

from ashare.data.cache import cache_exists, load_from_cache, save_to_cache
from ashare.data.providers import get_provider


_REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume", "turnover_rate"]
_PROVIDER_ENV = "ASHARE_DATA_PROVIDER"
_DEFAULT_PROVIDER = "baostock"


def _provider_name(provider: object) -> str:
    """Resolve provider name for cache keys."""
    env_name = os.getenv(_PROVIDER_ENV)
    if env_name:
        return env_name.lower()

    cls_name = provider.__class__.__name__.lower()
    if cls_name.endswith("provider"):
        return cls_name[:-8]

    return _DEFAULT_PROVIDER


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
    provider_name = _provider_name(provider)
    frequency = "30min"

    if cache_exists(provider_name, ts_code, frequency, start_date, end_date):
        df = load_from_cache(provider_name, ts_code, frequency, start_date, end_date)
        return _validate_loaded_frame(df, source="fetch_minute30")

    df = provider.fetch_minute30(ts_code, start_date, end_date)
    validated = _validate_loaded_frame(df, source="fetch_minute30")
    save_to_cache(provider_name, ts_code, frequency, start_date, end_date, validated)
    return validated


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
    provider_name = _provider_name(provider)
    frequency = "daily"

    if cache_exists(provider_name, ts_code, frequency, start_date, end_date):
        df = load_from_cache(provider_name, ts_code, frequency, start_date, end_date)
        return _validate_loaded_frame(df, source="fetch_daily")

    df = provider.fetch_daily(ts_code, start_date, end_date)
    validated = _validate_loaded_frame(df, source="fetch_daily")
    save_to_cache(provider_name, ts_code, frequency, start_date, end_date, validated)
    return validated
