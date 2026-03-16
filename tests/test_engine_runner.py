import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.runner import run_backtest
from ashare.strategies.mid_freq_ma import MidFreqMA


def _synthetic_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=50, freq="30min")
    close = [10 + (i * 0.05) for i in range(50)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.1 for c in close],
            "low": [c - 0.1 for c in close],
            "close": close,
            "volume": [1000] * 50,
            "turnover_rate": [2.0] * 50,
        },
        index=idx,
    )


def _run() -> dict:
    _, _, metrics = run_backtest(
        strategy_cls=MidFreqMA,
        data_df=_synthetic_df(),
        config=BacktestConfig(),
        strategy_params={"short_period": 3, "long_period": 8, "turnover_thresh": 1.0},
        symbol="SYNTH",
    )
    return metrics


def test_run_backtest_executes_and_returns_metrics() -> None:
    metrics = _run()

    assert isinstance(metrics, dict)
    for key in ["final_value", "total_return", "max_drawdown", "num_trades"]:
        assert key in metrics


def test_backtest_is_deterministic_for_same_input() -> None:
    r1 = _run()
    r2 = _run()

    assert r1["total_return"] == r2["total_return"]
    assert r1["final_value"] == r2["final_value"]
