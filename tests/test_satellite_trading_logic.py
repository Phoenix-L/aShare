from __future__ import annotations

import pandas as pd

from ashare.cli import _parse_param_options
from ashare.config.loader import load_strategy_config
from ashare.config.settings import BacktestConfig
from ashare.engine.runner import run_backtest
from ashare.strategies.core_satellite_mean_reversion import CoreSatelliteMeanReversion


def _synthetic_df(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="30min")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "volume": [1000] * len(closes),
            "turnover_rate": [2.0] * len(closes),
        },
        index=idx,
    )


def test_strategy_config_loads_yaml() -> None:
    cfg = load_strategy_config("configs/core_satellite.yaml")

    assert cfg["strategy"] == "core_satellite"
    assert cfg["core_position"] == 2000
    assert cfg["z_entry"] == [-1.5, -2.0, -2.5]
    assert cfg["z_exit"] == [0.8, 1.5]
    assert cfg["trend_filter"] is True


def test_cli_override_parses_list_params_for_strategy() -> None:
    parsed = _parse_param_options(
        (
            "z_entry=-1.5,-2.0,-2.5",
            "z_exit=0.8,1.2,1.5",
            "trade_unit=500",
        ),
        strategy_cls=CoreSatelliteMeanReversion,
    )

    assert parsed["z_entry"] == [[-1.5, -2.0, -2.5]]
    assert parsed["z_exit"] == [[0.8, 1.2, 1.5]]
    assert parsed["trade_unit"] == [500]


def test_entries_trigger_at_configured_z_entry_thresholds() -> None:
    closes = [100.0] * 160 + [98.0, 98.0]  # deep drop => entry and fill

    _, strat, _ = run_backtest(
        strategy_cls=CoreSatelliteMeanReversion,
        data_df=_synthetic_df(closes),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={
            "core_position": 2000,
            "satellite_max": 1000,
            "trade_unit": 500,
            "z_entry": [-1.0],
            "z_exit": [10.0],
            "trend_filter": False,
            "ma_short": 2,
            "ma_trend": 2,
        },
        symbol="SYNTH",
    )

    assert strat.buy_events >= 1
    assert strat.position.size >= 2500


def test_exits_trigger_at_configured_z_exit_thresholds_without_selling_core() -> None:
    closes = [100.0] * 160 + [98.0, 102.0, 102.0]  # entry then exit and fill

    _, strat, _ = run_backtest(
        strategy_cls=CoreSatelliteMeanReversion,
        data_df=_synthetic_df(closes),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={
            "core_position": 2000,
            "satellite_max": 1000,
            "trade_unit": 500,
            "z_entry": [-1.0],
            "z_exit": [1.0],
            "trend_filter": False,
            "ma_short": 2,
            "ma_trend": 2,
        },
        symbol="SYNTH",
    )

    assert strat.buy_events >= 1
    assert strat.sell_events >= 1
    assert strat.position.size >= 2000


def test_trend_filter_blocks_new_satellite_buy_below_ma120() -> None:
    closes = [100.0] * 160 + [95.0, 95.0]

    _, strat, _ = run_backtest(
        strategy_cls=CoreSatelliteMeanReversion,
        data_df=_synthetic_df(closes),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={
            "core_position": 2000,
            "satellite_max": 1000,
            "trade_unit": 500,
            "z_entry": [-1.0],
            "z_exit": [10.0],
            "trend_filter": True,
            "ma_short": 2,
            "ma_trend": 2,
        },
        symbol="SYNTH",
    )

    assert strat.buy_events == 0
    assert strat.position.size == 2000
