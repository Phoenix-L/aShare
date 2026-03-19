from __future__ import annotations

import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.runner import run_backtest
from ashare.strategies import get_strategy_class


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


def _config() -> BacktestConfig:
    return BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0)


def test_mean_reversion_starts_flat_without_entry_signal() -> None:
    strategy_cls = get_strategy_class("mean_reversion")
    closes = [100.0] * 170

    _, strat, _ = run_backtest(
        strategy_cls=strategy_cls,
        data_df=_synthetic_df(closes),
        config=_config(),
        strategy_params={"z_entry": -10.0, "z_exit": 10.0, "trade_unit": 500, "ma_short": 2, "ma_trend": 2},
        symbol="SYNTH",
    )

    assert strat.buy_events == 0
    assert strat.position.size == 0


def test_mean_reversion_entry_and_exit_trigger_correctly() -> None:
    strategy_cls = get_strategy_class("mean_reversion")
    closes = [100.0] * 160 + [98.0, 98.0, 102.0, 102.0]

    _, strat, metrics = run_backtest(
        strategy_cls=strategy_cls,
        data_df=_synthetic_df(closes),
        config=_config(),
        strategy_params={"z_entry": -1.0, "z_exit": 1.0, "trade_unit": 500, "ma_short": 2, "ma_trend": 2},
        symbol="SYNTH",
    )

    assert strat.buy_events >= 1
    assert strat.sell_events >= 1
    assert strat.position.size == 0
    assert metrics["num_trades"] > 0
