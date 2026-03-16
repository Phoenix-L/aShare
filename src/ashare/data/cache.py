"""Parquet-backed local cache helpers for market data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ashare.config.settings import get_cache_dir


def _cache_file_path(
    provider: str,
    symbol: str,
    frequency: str,
    start: str,
    end: str,
) -> Path:
    """Build deterministic cache file path for a request tuple."""
    cache_root = Path(get_cache_dir())
    filename = f"{start}_{end}.parquet"
    return cache_root / provider / symbol / frequency / filename


def cache_exists(provider: str, symbol: str, frequency: str, start: str, end: str) -> bool:
    """Return whether a cache file exists for the request tuple."""
    return _cache_file_path(provider, symbol, frequency, start, end).exists()


def load_from_cache(
    provider: str,
    symbol: str,
    frequency: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Load cached data from parquet for the request tuple."""
    return pd.read_parquet(_cache_file_path(provider, symbol, frequency, start, end))


def save_to_cache(
    provider: str,
    symbol: str,
    frequency: str,
    start: str,
    end: str,
    dataframe: pd.DataFrame,
) -> Path:
    """Persist dataframe to local parquet cache and return target path."""
    path = _cache_file_path(provider, symbol, frequency, start, end)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        dataframe.to_parquet(path)
    except ImportError:
        # Optional parquet engine is unavailable; skip writing cache.
        pass
    return path
