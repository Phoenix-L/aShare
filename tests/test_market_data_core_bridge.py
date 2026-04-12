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
