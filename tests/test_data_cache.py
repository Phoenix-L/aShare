from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ashare.data import cache, loaders


class CountingProvider:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df
        self.daily_calls = 0
        self.minute_calls = 0

    def fetch_daily(self, _ts_code: str, _start_date: str, _end_date: str) -> pd.DataFrame:
        self.daily_calls += 1
        return self.df

    def fetch_minute30(self, _ts_code: str, _start_date: str, _end_date: str) -> pd.DataFrame:
        self.minute_calls += 1
        return self.df


@pytest.fixture
def sample_df() -> pd.DataFrame:
    idx = pd.to_datetime(["2024-01-01", "2024-01-02"])
    return pd.DataFrame(
        {
            "open": [10.0, 10.5],
            "high": [10.8, 11.0],
            "low": [9.8, 10.2],
            "close": [10.6, 10.9],
            "volume": [1000, 1200],
            "turnover_rate": [0.35, 0.41],
        },
        index=idx,
    )


@pytest.fixture
def parquet_shim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shim parquet calls to pickle so tests stay self-contained."""

    def _to_parquet(df: pd.DataFrame, path: str | Path) -> None:
        df.to_pickle(path)

    def _read_parquet(path: str | Path) -> pd.DataFrame:
        return pd.read_pickle(path)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _to_parquet)
    monkeypatch.setattr(cache.pd, "read_parquet", _read_parquet)


def test_cache_save_and_load_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    sample_df: pd.DataFrame,
    parquet_shim: None,
) -> None:
    monkeypatch.setenv("ASHARE_CACHE_DIR", str(tmp_path))

    saved_path = cache.save_to_cache("tushare", "600519.SH", "30min", "20240101", "20250101", sample_df)

    assert saved_path.exists()
    loaded = cache.load_from_cache("tushare", "600519.SH", "30min", "20240101", "20250101")
    pd.testing.assert_frame_equal(loaded, sample_df)


def test_cache_exists_behavior(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    sample_df: pd.DataFrame,
    parquet_shim: None,
) -> None:
    monkeypatch.setenv("ASHARE_CACHE_DIR", str(tmp_path))

    assert not cache.cache_exists("baostock", "000001.SZ", "daily", "20240101", "20240131")

    cache.save_to_cache("baostock", "000001.SZ", "daily", "20240101", "20240131", sample_df)

    assert cache.cache_exists("baostock", "000001.SZ", "daily", "20240101", "20240131")


def test_loader_cache_hit_skips_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    sample_df: pd.DataFrame,
    parquet_shim: None,
) -> None:
    monkeypatch.setenv("ASHARE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("ASHARE_DATA_PROVIDER", "baostock")
    provider = CountingProvider(sample_df)
    monkeypatch.setattr(loaders, "get_provider", lambda: provider)

    cache.save_to_cache("baostock", "000001.SZ", "daily", "20240101", "20240131", sample_df)

    loaded = loaders.load_daily("000001.SZ", "20240101", "20240131")

    assert provider.daily_calls == 0
    pd.testing.assert_frame_equal(loaded, sample_df)


def test_loader_cache_miss_fetches_and_persists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    sample_df: pd.DataFrame,
    parquet_shim: None,
) -> None:
    monkeypatch.setenv("ASHARE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("ASHARE_DATA_PROVIDER", "baostock")
    provider = CountingProvider(sample_df)
    monkeypatch.setattr(loaders, "get_provider", lambda: provider)

    loaded = loaders.load_minute_30("000001.SZ", "20240101", "20240131")

    assert provider.minute_calls == 1
    assert cache.cache_exists("baostock", "000001.SZ", "30min", "20240101", "20240131")
    pd.testing.assert_frame_equal(loaded, sample_df)


def test_loader_use_cache_false_bypasses_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    sample_df: pd.DataFrame,
    parquet_shim: None,
) -> None:
    monkeypatch.setenv("ASHARE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("ASHARE_DATA_PROVIDER", "baostock")
    provider = CountingProvider(sample_df)
    monkeypatch.setattr(loaders, "get_provider", lambda: provider)

    cache.save_to_cache("baostock", "000001.SZ", "daily", "20240101", "20240131", sample_df)

    loaded = loaders.load_daily("000001.SZ", "20240101", "20240131", use_cache=False)

    assert provider.daily_calls == 1
    pd.testing.assert_frame_equal(loaded, sample_df)
