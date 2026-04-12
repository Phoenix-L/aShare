from __future__ import annotations

import importlib
import sys
import types

import pandas as pd



def _sample_df() -> pd.DataFrame:
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


def test_bridge_fallback_without_market_data_core(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "market_data_core.access", raising=False)
    monkeypatch.delitem(sys.modules, "market_data_core.validation", raising=False)
    monkeypatch.delitem(sys.modules, "market_data_core.calendar", raising=False)
    monkeypatch.delitem(sys.modules, "market_data_core.contracts.bars", raising=False)
    monkeypatch.delitem(sys.modules, "market_data_core.contracts", raising=False)
    monkeypatch.delitem(sys.modules, "market_data_core", raising=False)

    bridge = importlib.reload(importlib.import_module("ashare.data.core_bridge"))

    assert bridge.using_market_data_core() is False
    assert bridge.canonical_bar_columns() == (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover_rate",
    )
    validated = bridge.validate_canonical_frame(_sample_df(), source="test")
    assert isinstance(validated, pd.DataFrame)
    assert bridge.load_daily_from_core(symbol="000001.SZ", start="2024-01-01", end="2024-01-02") is None


def test_bridge_delegates_to_market_data_core_contracts(monkeypatch) -> None:
    fake_mdc = types.ModuleType("market_data_core")
    fake_contracts = types.ModuleType("market_data_core.contracts")
    fake_bars = types.ModuleType("market_data_core.contracts.bars")

    fake_bars.CANONICAL_BAR_COLUMNS = (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover_rate",
    )

    called = {"count": 0}

    def _validator(df: pd.DataFrame) -> pd.DataFrame:
        called["count"] += 1
        return df.sort_index()

    fake_bars.validate_canonical_bar_frame = _validator

    monkeypatch.setitem(sys.modules, "market_data_core", fake_mdc)
    monkeypatch.setitem(sys.modules, "market_data_core.contracts", fake_contracts)
    monkeypatch.setitem(sys.modules, "market_data_core.contracts.bars", fake_bars)

    bridge = importlib.reload(importlib.import_module("ashare.data.core_bridge"))

    assert bridge.using_market_data_core() is True
    assert bridge.canonical_bar_columns() == fake_bars.CANONICAL_BAR_COLUMNS

    validated = bridge.validate_canonical_frame(_sample_df().iloc[::-1], source="delegated")
    assert called["count"] == 1
    assert validated.index.is_monotonic_increasing


def test_bridge_uses_phase5_access_validation_and_calendar(monkeypatch) -> None:
    fake_mdc = types.ModuleType("market_data_core")
    fake_access = types.ModuleType("market_data_core.access")
    fake_validation = types.ModuleType("market_data_core.validation")
    fake_calendar = types.ModuleType("market_data_core.calendar")
    fake_contracts = types.ModuleType("market_data_core.contracts")
    fake_bars = types.ModuleType("market_data_core.contracts.bars")
    fake_bars.CANONICAL_BAR_COLUMNS = ("open", "high", "low", "close", "volume", "turnover_rate")
    fake_bars.validate_canonical_bar_frame = lambda df: df

    calls: dict[str, object] = {}

    def _load_daily(*, symbol: str, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
        calls["daily"] = (symbol, start, end, use_cache)
        return _sample_df()

    def _load_30m(*, symbol: str, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
        calls["30m"] = (symbol, start, end, use_cache)
        return _sample_df()

    def _list_datasets(*, data_root: str | None = None) -> list[str]:
        calls["list"] = data_root
        return ["cn_equity_1d_raw"]

    def _inspect_dataset(*, dataset_id: str, data_root: str | None = None) -> dict[str, object]:
        calls["inspect"] = (dataset_id, data_root)
        return {"dataset_id": dataset_id, "frequency": "1d"}

    def _validate_bars(*, df: pd.DataFrame, frequency: str, market: str = "cn_equity", strict: bool = True):
        calls["validate"] = (frequency, market, strict, len(df))
        return types.SimpleNamespace(ok=True, errors=[], warnings=[], stats={})

    fake_access.load_daily = _load_daily
    fake_access.load_30m = _load_30m
    fake_access.list_datasets = _list_datasets
    fake_access.inspect_dataset = _inspect_dataset
    fake_validation.validate_bars = _validate_bars
    fake_calendar.session_open_anchors = lambda *, trading_day, frequency: (trading_day, frequency)
    fake_calendar.is_session_aligned = lambda *, timestamp, frequency: frequency == "30m"

    monkeypatch.setitem(sys.modules, "market_data_core", fake_mdc)
    monkeypatch.setitem(sys.modules, "market_data_core.access", fake_access)
    monkeypatch.setitem(sys.modules, "market_data_core.validation", fake_validation)
    monkeypatch.setitem(sys.modules, "market_data_core.calendar", fake_calendar)
    monkeypatch.setitem(sys.modules, "market_data_core.contracts", fake_contracts)
    monkeypatch.setitem(sys.modules, "market_data_core.contracts.bars", fake_bars)

    bridge = importlib.reload(importlib.import_module("ashare.data.core_bridge"))

    assert isinstance(bridge.load_daily_from_core(symbol="000001.SZ", start="2024-01-01", end="2024-01-02"), pd.DataFrame)
    assert isinstance(bridge.load_30m_from_core(symbol="000001.SZ", start="2024-01-01", end="2024-01-02"), pd.DataFrame)
    assert bridge.list_datasets_from_core() == ["cn_equity_1d_raw"]
    assert bridge.inspect_dataset_from_core("cn_equity_1d_raw")["frequency"] == "1d"
    assert bridge.is_session_aligned_from_core(timestamp=pd.Timestamp("2024-01-01 09:30"), frequency="30m") is True
    assert bridge.validate_canonical_frame(_sample_df(), source="load_minute_30").shape[0] == 2
    assert calls["daily"] == ("000001.SZ", "2024-01-01", "2024-01-02", True)
    assert calls["30m"] == ("000001.SZ", "2024-01-01", "2024-01-02", True)
    assert calls["validate"] == ("30m", "cn_equity", True, 2)
