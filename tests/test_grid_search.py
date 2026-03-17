from pathlib import Path

import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.experiment.executor import execute_experiment_spec
from ashare.experiment.grid import expand_grid
from ashare.strategies.mean_reversion_advanced import MeanReversionAdvanced


def _synthetic_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=80, freq="30min")
    close = [100.0 + i * 0.01 for i in range(80)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.2 for c in close],
            "low": [c - 0.2 for c in close],
            "close": close,
            "volume": [1000] * len(close),
            "turnover_rate": [2.0] * len(close),
        },
        index=idx,
    )


def test_expand_grid_cross_product() -> None:
    grid = {"z_entry": [-1.2, -1.5, -1.8], "z_exit": [0.3, 0.5]}

    combos = expand_grid(grid)

    assert len(combos) == 6
    assert {"z_entry": -1.2, "z_exit": 0.3} in combos
    assert {"z_entry": -1.8, "z_exit": 0.5} in combos


def test_run_experiment_injects_params_and_executes_all_runs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

    captured: list[dict] = []

    def _fake_backtest(strategy_cls, data_df, config, strategy_params=None, symbol=None, experiment_name=None, run_id=None):
        _ = (strategy_cls, data_df, config, symbol, experiment_name, run_id)
        captured.append(dict(strategy_params or {}))
        return None, None, {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    experiment_name = "test_grid_search"
    result = execute_experiment_spec(
        strategy_cls=MeanReversionAdvanced,
        strategy_name="mean_reversion_advanced",
        spec={
            "name": experiment_name,
            "strategy": "mean_reversion_advanced",
            "symbols": ["600519.SH"],
            "start": "2024-01-01",
            "end": "2024-01-05",
            "parameters": {"trade_unit": 500, "use_trend_filter": True, "use_art_filter": True},
            "grid": {"z_entry": [-1.2, -1.5, -1.8], "z_exit": [0.3, 0.5]},
        },
        config=BacktestConfig(),
    )

    assert result["num_runs"] == 6
    assert len(captured) == 6
    assert {"trade_unit": 500, "use_trend_filter": True, "use_art_filter": True, "z_entry": -1.2, "z_exit": 0.3} in captured
    assert {"trade_unit": 500, "use_trend_filter": True, "use_art_filter": True, "z_entry": -1.8, "z_exit": 0.5} in captured
    assert len(result["results"]) == 6
