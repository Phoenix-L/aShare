import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.runner import run_backtest
from ashare.strategies import get_strategy_class
from ashare.strategies.core_satellite_mean_reversion import CoreSatelliteMeanReversion


def _synthetic_df(rows: int = 220) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="30min")
    close = [100 + i * 0.05 for i in range(rows)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.5 for c in close],
            "low": [c - 0.5 for c in close],
            "close": close,
            "volume": [1000] * rows,
            "turnover_rate": [1.5] * rows,
        },
        index=idx,
    )


def test_core_satellite_strategy_runs_on_synthetic_data() -> None:
    strategy_cls = get_strategy_class("core_satellite")

    _, _, metrics = run_backtest(
        strategy_cls=strategy_cls,
        data_df=_synthetic_df(),
        config=BacktestConfig(commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={"ma_short": 2, "ma_trend": 2, "trend_filter": False},
        symbol="SYNTH",
    )

    assert isinstance(metrics, dict)
    assert "final_value" in metrics


def test_core_satellite_z_entry_mode_placeholder_default_and_override() -> None:
    assert CoreSatelliteMeanReversion.params.z_entry_mode == "ladder"

    strategy_cls = get_strategy_class("core_satellite")
    _, strat, _ = run_backtest(
        strategy_cls=strategy_cls,
        data_df=_synthetic_df(),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={"z_entry_mode": "ladder", "ma_short": 2, "ma_trend": 2, "trend_filter": False},
        symbol="SYNTH",
    )

    assert strat.p.z_entry_mode == "ladder"
