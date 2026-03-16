import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.runner import run_backtest
from ashare.strategies.mid_freq_ma import MidFreqMA


def _crossover_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=18, freq="30min")
    close = [12, 11.5, 11, 10.5, 10, 10.2, 10.5, 11, 11.6, 12.2, 12, 11.7, 11.2, 10.8, 10.4, 10.1, 9.8, 9.6]

    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.1 for c in close],
            "low": [c - 0.1 for c in close],
            "close": close,
            "volume": [1000] * len(close),
            "turnover_rate": [2.0] * len(close),
        },
        index=idx,
    )


def test_moving_average_crossover_generates_expected_signal(monkeypatch) -> None:
    monkeypatch.setattr("ashare.strategies.mid_freq_ma.calc_buy_size", lambda cash, price, lot=100: 100)

    _, _, metrics = run_backtest(
        strategy_cls=MidFreqMA,
        data_df=_crossover_df(),
        config=BacktestConfig(commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={"short_period": 3, "long_period": 6, "turnover_thresh": 1.0},
        symbol="SYNTH",
    )

    assert metrics["num_trades"] > 0


def test_strategy_parameters_accepted() -> None:
    _, _, metrics = run_backtest(
        strategy_cls=MidFreqMA,
        data_df=_crossover_df(),
        config=BacktestConfig(commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={"short_period": 2, "long_period": 7, "turnover_thresh": 0.5},
        symbol="SYNTH",
    )

    assert isinstance(metrics, dict)


def test_no_crash_on_small_dataset() -> None:
    _, _, metrics = run_backtest(
        strategy_cls=MidFreqMA,
        data_df=_crossover_df().head(10),
        config=BacktestConfig(commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={"short_period": 3, "long_period": 9, "turnover_thresh": 1.0},
        symbol="SYNTH",
    )

    assert "final_value" in metrics
