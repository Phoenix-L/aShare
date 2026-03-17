from pathlib import Path

import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.experiment.executor import execute_experiment_spec
from ashare.research.experiment_runner import generate_param_combinations
from ashare.strategies.mid_freq_ma import MidFreqMA


def _synthetic_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=60, freq="30min")
    close = [10 + (i * 0.05) for i in range(60)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.1 for c in close],
            "low": [c - 0.1 for c in close],
            "close": close,
            "volume": [1000] * 60,
            "turnover_rate": [2.0] * 60,
        },
        index=idx,
    )


def test_generate_param_combinations_expands_cross_product() -> None:
    param_grid = {
        "short_period": [5, 10, 15],
        "long_period": [20, 30],
    }

    combos = generate_param_combinations(param_grid)

    assert len(combos) == 6
    assert {"short_period": 5, "long_period": 20} in combos
    assert {"short_period": 15, "long_period": 30} in combos


def test_run_experiment_creates_outputs_and_metrics(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

    def _fake_backtest(
        strategy_cls,
        data_df,
        config,
        strategy_params=None,
        symbol=None,
        experiment_name=None,
        run_id=None,
    ):
        _ = (strategy_cls, data_df, config, strategy_params, symbol, experiment_name, run_id)
        return None, None, {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1, "num_trades": 1}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    experiment_name = "test_experiment"
    result = execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="mid_freq_ma",
        spec={
            "name": experiment_name,
            "strategy": "mid_freq_ma",
            "symbols": ["600519.SH", "000858.SZ"],
            "start": "2024-01-01",
            "end": "2024-01-20",
            "parameters": {},
            "grid": {"short_period": [3, 5], "long_period": [8], "turnover_thresh": [1.0]},
        },
        config=BacktestConfig(),
    )

    experiment_dir = Path(result["output_dir"])
    results_path = Path(result["summary_path"])
    results_sorted_path = Path(result["summary_sorted_path"])

    assert experiment_dir.exists()
    assert results_path.exists()
    assert results_sorted_path.exists()

    results_df = pd.read_csv(results_path)
    assert len(results_df) == 4
    assert set(["run_id", "total_return", "sharpe", "max_drawdown"]).issubset(results_df.columns)

    assert results_df["total_return"].notna().all()
    assert results_df["max_drawdown"].notna().all()
