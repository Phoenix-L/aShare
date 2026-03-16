from __future__ import annotations

import pandas as pd
import pytest

from ashare.data import loaders
from ashare.data.providers import get_provider, reset_provider


class DummyProvider:
    def __init__(self, df: pd.DataFrame | None = None) -> None:
        self._df = df

    def fetch_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self._df is None:
            raise RuntimeError("provider failure")
        return self._df

    def fetch_minute30(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self._df is None:
            raise RuntimeError("provider failure")
        return self._df


def _valid_df() -> pd.DataFrame:
    idx = pd.to_datetime(["2024-01-01", "2024-01-02"])
    return pd.DataFrame(
        {
            "open": [1.0, 1.1],
            "high": [1.2, 1.3],
            "low": [0.9, 1.0],
            "close": [1.1, 1.2],
            "volume": [100, 120],
            "turnover_rate": [0.3, 0.4],
        },
        index=idx,
    )


def test_provider_selection_logic_defaults_to_baostock(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeBao:
        def fetch_daily(self, *_args):
            return _valid_df()

        def fetch_minute30(self, *_args):
            return _valid_df()

    reset_provider()
    monkeypatch.delenv("ASHARE_DATA_PROVIDER", raising=False)
    monkeypatch.setattr("ashare.data.providers.baostock_provider.BaoStockProvider", FakeBao)

    provider = get_provider()

    assert isinstance(provider, FakeBao)
    reset_provider()


def test_load_daily_schema_validation_with_mocked_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loaders, "get_provider", lambda: DummyProvider(_valid_df()))

    df = loaders.load_daily("000001.SZ", "2024-01-01", "2024-01-02")

    assert list(df.columns) == ["open", "high", "low", "close", "volume", "turnover_rate"]
    assert df.index.is_monotonic_increasing


def test_loader_failure_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loaders, "get_provider", lambda: DummyProvider(None))

    with pytest.raises(RuntimeError, match="provider failure"):
        loaders.load_minute_30("000001.SZ", "2024-01-01", "2024-01-02")


def test_loader_rejects_missing_required_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = _valid_df().drop(columns=["turnover_rate"])
    monkeypatch.setattr(loaders, "get_provider", lambda: DummyProvider(bad))

    with pytest.raises(ValueError, match="missing required columns"):
        loaders.load_daily("000001.SZ", "2024-01-01", "2024-01-02")
